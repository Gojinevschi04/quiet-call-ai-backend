import asyncio
import json
from collections import defaultdict
from datetime import datetime

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class CallEventBroadcaster:
    """In-memory pub/sub for broadcasting call events to WebSocket clients."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, task_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[task_id].add(websocket)
        logger.info("WS client connected for task %d", task_id)

    async def disconnect(self, task_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info("WS client disconnected for task %d", task_id)

    async def emit(self, task_id: int, event: str, data: dict | None = None) -> None:
        message = {
            "event": event,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            **(data or {}),
        }
        async with self._lock:
            clients = set(self._connections.get(task_id, set()))

        for websocket in clients:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                logger.debug("Failed to send WS message for task %d, disconnecting client", task_id)
                await self.disconnect(task_id, websocket)

    def has_listeners(self, task_id: int) -> bool:
        return bool(self._connections.get(task_id))


call_broadcaster = CallEventBroadcaster()
