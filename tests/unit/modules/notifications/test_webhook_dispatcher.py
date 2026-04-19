from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.notifications.webhook_dispatcher import send_task_webhook
from app.modules.tasks.models import Task


@pytest.mark.asyncio
async def test_send_task_webhook_no_url_is_noop(mock_task: Task) -> None:
    with patch("app.modules.notifications.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        await send_task_webhook("", mock_task)
        mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_send_task_webhook_posts_expected_payload(mock_task: Task) -> None:
    mock_response = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ):
        await send_task_webhook("https://example.com/hook", mock_task)

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args.args[0] == "https://example.com/hook"
    payload = call_args.kwargs["json"]
    assert payload["event"] == "task.status_change"
    assert payload["task_id"] == mock_task.id
    assert payload["target_phone"] == mock_task.target_phone
    assert payload["template_id"] == mock_task.template_id
    assert payload["summary"] == mock_task.summary
    assert payload["error_reason"] == mock_task.error_reason
    assert payload["created_at"] == mock_task.created_at.isoformat()
    assert payload["updated_at"] == mock_task.updated_at.isoformat()


@pytest.mark.asyncio
async def test_send_task_webhook_uses_configured_timeout(mock_task: Task) -> None:
    from app.modules.notifications.webhook_dispatcher import WEBHOOK_TIMEOUT_SECONDS

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ) as mock_client_cls:
        await send_task_webhook("https://example.com/hook", mock_task)

    mock_client_cls.assert_called_once_with(timeout=WEBHOOK_TIMEOUT_SECONDS)


@pytest.mark.asyncio
async def test_send_task_webhook_swallows_network_error(mock_task: Task) -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ):
        await send_task_webhook("https://example.com/hook", mock_task)


@pytest.mark.asyncio
async def test_send_task_webhook_swallows_timeout(mock_task: Task) -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ):
        await send_task_webhook("https://example.com/hook", mock_task)


@pytest.mark.asyncio
async def test_send_task_webhook_logs_on_non_2xx(mock_task: Task) -> None:
    mock_response = MagicMock(status_code=500)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ), patch("app.modules.notifications.webhook_dispatcher.logger") as mock_logger:
        await send_task_webhook("https://example.com/hook", mock_task)

    mock_logger.info.assert_called_once()
    message = mock_logger.info.call_args.args[0]
    assert "Webhook delivered" in message


@pytest.mark.asyncio
async def test_send_task_webhook_handles_none_timestamps() -> None:
    task = MagicMock(spec=Task)
    task.id = 1
    task.status = "completed"
    task.target_phone = "+37312345678"
    task.template_id = 1
    task.summary = None
    task.error_reason = None
    task.created_at = None
    task.updated_at = None

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
    mock_client_ctx = MagicMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.modules.notifications.webhook_dispatcher.httpx.AsyncClient",
        return_value=mock_client_ctx,
    ):
        await send_task_webhook("https://example.com/hook", task)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["created_at"] is None
    assert payload["updated_at"] is None
