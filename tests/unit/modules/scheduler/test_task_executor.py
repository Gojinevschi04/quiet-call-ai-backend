from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.tasks.schema import TaskStatus


def _stub_task_repo(task_mock: MagicMock | None = None) -> MagicMock:
    repo = MagicMock()
    repo.get_by_id_any_user = AsyncMock(return_value=task_mock)
    return repo


def _patch_session_and_task_repo(task: MagicMock | None) -> tuple:
    session_patch = patch("app.modules.scheduler.task_executor.AsyncSession")
    task_repo_patch = patch(
        "app.modules.tasks.repository.TaskRepository",
        return_value=_stub_task_repo(task),
    )
    return session_patch, task_repo_patch


@pytest.mark.asyncio
async def test_execute_due_task_success_legacy_path() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    task_in_db = MagicMock()
    task_in_db.error_reason = None
    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=MagicMock(status=TaskStatus.COMPLETED))

    session_patch, task_repo_patch = _patch_session_and_task_repo(task_in_db)
    with session_patch as mock_session_cls, task_repo_patch, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.integrations.call_manager.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)

    mock_manager.execute_task.assert_awaited_once_with(1, 10)


@pytest.mark.asyncio
async def test_execute_due_task_success_realtime_path() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    task_in_db = MagicMock()
    task_in_db.error_reason = None
    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=MagicMock(status=TaskStatus.COMPLETED))

    session_patch, task_repo_patch = _patch_session_and_task_repo(task_in_db)
    with session_patch as mock_session_cls, task_repo_patch, \
         patch("app.core.config.settings.USE_REALTIME_API", True), \
         patch("app.integrations.realtime_call_manager.RealtimeCallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)

    mock_manager.execute_task.assert_awaited_once_with(1, 10)


@pytest.mark.asyncio
async def test_execute_due_task_falls_back_to_legacy_when_prior_realtime_init_failed() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    task_in_db = MagicMock()
    task_in_db.error_reason = "[REALTIME_INIT_FAILED] connection refused"
    legacy_manager = MagicMock()
    legacy_manager.execute_task = AsyncMock(return_value=MagicMock(status=TaskStatus.COMPLETED))
    realtime_manager = MagicMock()
    realtime_manager.execute_task = AsyncMock()

    session_patch, task_repo_patch = _patch_session_and_task_repo(task_in_db)
    with session_patch as mock_session_cls, task_repo_patch, \
         patch("app.core.config.settings.USE_REALTIME_API", True), \
         patch("app.integrations.call_manager.CallManager", return_value=legacy_manager), \
         patch("app.integrations.realtime_call_manager.RealtimeCallManager", return_value=realtime_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)

    legacy_manager.execute_task.assert_awaited_once_with(1, 10)
    realtime_manager.execute_task.assert_not_called()


@pytest.mark.asyncio
async def test_execute_due_task_failure() -> None:
    from app.modules.scheduler.task_executor import execute_due_task

    task_in_db = MagicMock()
    task_in_db.error_reason = None
    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(side_effect=RuntimeError("Call failed"))

    session_patch, task_repo_patch = _patch_session_and_task_repo(task_in_db)
    with session_patch as mock_session_cls, task_repo_patch, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.integrations.call_manager.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await execute_due_task(task_id=1, user_id=10)
