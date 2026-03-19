from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ws_manager import CallEventBroadcaster


@pytest.mark.asyncio
async def test_connect_and_disconnect() -> None:
    broadcaster = CallEventBroadcaster()
    ws = AsyncMock()

    await broadcaster.connect(1, ws)
    ws.accept.assert_called_once()
    assert broadcaster.has_listeners(1)

    await broadcaster.disconnect(1, ws)
    assert not broadcaster.has_listeners(1)


@pytest.mark.asyncio
async def test_emit_sends_to_connected_clients() -> None:
    broadcaster = CallEventBroadcaster()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await broadcaster.connect(1, ws1)
    await broadcaster.connect(1, ws2)

    await broadcaster.emit(1, "status_change", {"status": "in_progress"})

    assert ws1.send_text.call_count == 1
    assert ws2.send_text.call_count == 1
    sent = ws1.send_text.call_args[0][0]
    assert '"event": "status_change"' in sent
    assert '"task_id": 1' in sent


@pytest.mark.asyncio
async def test_emit_does_nothing_without_listeners() -> None:
    broadcaster = CallEventBroadcaster()
    await broadcaster.emit(1, "test_event")


@pytest.mark.asyncio
async def test_emit_disconnects_failed_client() -> None:
    broadcaster = CallEventBroadcaster()
    ws_good = AsyncMock()
    ws_bad = AsyncMock()
    ws_bad.send_text.side_effect = RuntimeError("connection closed")

    await broadcaster.connect(1, ws_good)
    await broadcaster.connect(1, ws_bad)

    await broadcaster.emit(1, "message", {"text": "hello"})

    ws_good.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_has_listeners_false_for_unknown_task() -> None:
    broadcaster = CallEventBroadcaster()
    assert not broadcaster.has_listeners(999)


@pytest.mark.asyncio
async def test_multiple_tasks_independent() -> None:
    broadcaster = CallEventBroadcaster()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await broadcaster.connect(1, ws1)
    await broadcaster.connect(2, ws2)

    await broadcaster.emit(1, "dialing")
    assert ws1.send_text.call_count == 1
    assert ws2.send_text.call_count == 0
