"""Fire-and-forget outbound webhook dispatcher.

Users can configure a `webhook_url` on their profile. When a task reaches a
terminal state (COMPLETED / FAILED), we POST a JSON payload to that URL.
All failures are swallowed — webhook delivery never blocks or fails the call.
"""

import httpx

from app.core.logging import get_logger
from app.modules.tasks.models import Task

logger = get_logger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10.0


async def send_task_webhook(webhook_url: str, task: Task) -> None:
    """Send a task-status notification to the user's configured webhook URL."""
    if not webhook_url:
        return

    payload = {
        "event": "task.status_change",
        "task_id": task.id,
        "status": task.status,
        "target_phone": task.target_phone,
        "template_id": task.template_id,
        "summary": task.summary,
        "error_reason": task.error_reason,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(webhook_url, json=payload)
            logger.info(
                "Webhook delivered to %s: status=%d task=%d",
                webhook_url, response.status_code, task.id,
            )
    except Exception:
        logger.exception("Webhook delivery failed for task %d to %s", task.id, webhook_url)
