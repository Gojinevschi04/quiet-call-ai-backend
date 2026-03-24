from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.tasks.schema import TaskStatus


@pytest.mark.asyncio
async def test_execute_due_task_success_legacy_path() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    mock_task = MagicMock()
    mock_task.status = TaskStatus.COMPLETED

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=mock_task)

    with patch("app.modules.scheduler.task_executor.AsyncSession") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.integrations.call_manager.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)

        mock_manager.execute_task.assert_called_once_with(1, 10)


@pytest.mark.asyncio
async def test_execute_due_task_success_realtime_path() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    mock_task = MagicMock()
    mock_task.status = TaskStatus.COMPLETED

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=mock_task)

    with patch("app.modules.scheduler.task_executor.AsyncSession") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", True), \
         patch("app.integrations.realtime_call_manager.RealtimeCallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)

        mock_manager.execute_task.assert_called_once_with(1, 10)


@pytest.mark.asyncio
async def test_execute_due_task_failure() -> None:
    """Task execution failure should be logged but not re-raised."""
    from app.modules.scheduler.task_executor import execute_due_task

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(side_effect=RuntimeError("Call failed"))

    with patch("app.modules.scheduler.task_executor.AsyncSession") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.integrations.call_manager.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)
