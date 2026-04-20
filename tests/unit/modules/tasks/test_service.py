from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.tasks.exceptions import (
    InvalidTaskDataError,
    TaskNotCancellableError,
    TaskNotEditableError,
    TaskNotFoundError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskCreate, TaskEditRequest, TaskStatus
from app.modules.tasks.service import TaskService
from app.modules.templates.exceptions import TemplateNotFoundError
from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository


@pytest.mark.asyncio
async def test_create_task_success(mock_task: Task, mock_template: DialogTemplate) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.create = AsyncMock(return_value=mock_task)
    mock_task_repo.count_by_phone_in_last_24h = AsyncMock(return_value=0)
    mock_task_repo.count_by_user_in_last_24h = AsyncMock(return_value=0)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={"preferred_date": "2026-03-20", "preferred_time": "10:00"},
    )
    result = await service.create_task(data, user_id=1)

    assert result == mock_task
    mock_task_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_task_template_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=None)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(target_phone="+37312345678", template_id=999, slot_data={})

    with pytest.raises(TemplateNotFoundError):
        await service.create_task(data, user_id=1)


@pytest.mark.asyncio
async def test_create_task_missing_slots(mock_template: DialogTemplate) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(target_phone="+37312345678", template_id=1, slot_data={})

    with pytest.raises(InvalidTaskDataError, match="Missing required slots"):
        await service.create_task(data, user_id=1)


@pytest.mark.asyncio
async def test_get_task_success(mock_task: Task) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.get_task(1, user_id=1)

    assert result == mock_task


@pytest.mark.asyncio
async def test_get_task_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotFoundError):
        await service.get_task(999, user_id=1)


@pytest.mark.asyncio
async def test_cancel_task_success(mock_task: Task) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.cancel_task(1, user_id=1)

    assert result.status == TaskStatus.FAILED
    assert result.error_reason == "Cancelled by user"


@pytest.mark.asyncio
async def test_cancel_task_not_cancellable(mock_task: Task) -> None:
    mock_task.status = TaskStatus.IN_PROGRESS
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotCancellableError):
        await service.cancel_task(1, user_id=1)


@pytest.mark.asyncio
async def test_get_stats() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_by_status = AsyncMock(
        return_value={TaskStatus.PENDING: 2, TaskStatus.COMPLETED: 5, TaskStatus.FAILED: 1}
    )
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    stats = await service.get_stats(user_id=1)

    assert stats.total == 8
    assert stats.pending == 2
    assert stats.completed == 5
    assert stats.failed == 1
    assert stats.in_progress == 0


@pytest.mark.asyncio
async def test_create_task_with_scheduled_time(mock_template: DialogTemplate) -> None:
    future_time = (datetime.now() + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    scheduled_task = Task(
        id=2,
        target_phone="+37312345678",
        status=TaskStatus.SCHEDULED,
        template_id=1,
        user_id=1,
        slot_data={"preferred_date": "2026-03-20", "preferred_time": "10:00"},
        scheduled_time=future_time,
    )
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.create = AsyncMock(return_value=scheduled_task)
    mock_task_repo.count_by_phone_in_last_24h = AsyncMock(return_value=0)
    mock_task_repo.count_by_user_in_last_24h = AsyncMock(return_value=0)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={"preferred_date": "2026-03-20", "preferred_time": "10:00"},
        scheduled_time=future_time.isoformat(),
    )
    result = await service.create_task(data, user_id=1)

    assert result.status == TaskStatus.SCHEDULED
    assert result.scheduled_time is not None
    created_task = mock_task_repo.create.call_args[0][0]
    assert created_task.status == TaskStatus.SCHEDULED


@pytest.mark.asyncio
async def test_get_tasks_paginated(mock_task: Task) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_all_paginated = AsyncMock(return_value=([mock_task], 1))
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    tasks, total = await service.get_tasks(user_id=1, limit=20, offset=0)

    assert len(tasks) == 1
    assert total == 1
    mock_task_repo.get_all_paginated.assert_called_once_with(1, 20, 0, None)


@pytest.mark.asyncio
async def test_get_tasks_with_status_filter(mock_task: Task) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_all_paginated = AsyncMock(return_value=([mock_task], 1))
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    tasks, total = await service.get_tasks(user_id=1, limit=10, offset=0, status=TaskStatus.PENDING)

    assert len(tasks) == 1
    mock_task_repo.get_all_paginated.assert_called_once_with(1, 10, 0, TaskStatus.PENDING)


@pytest.mark.asyncio
async def test_get_tasks_empty() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_all_paginated = AsyncMock(return_value=([], 0))
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    tasks, total = await service.get_tasks(user_id=1)

    assert len(tasks) == 0
    assert total == 0


@pytest.mark.asyncio
async def test_cancel_scheduled_task(mock_task: Task) -> None:
    mock_task.status = TaskStatus.SCHEDULED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.cancel_task(1, user_id=1)

    assert result.status == TaskStatus.FAILED
    assert result.error_reason == "Cancelled by user"


@pytest.mark.asyncio
async def test_get_stats_empty() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_by_status = AsyncMock(return_value={})
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    stats = await service.get_stats(user_id=1)

    assert stats.total == 0
    assert stats.pending == 0
    assert stats.completed == 0
    assert stats.failed == 0
    assert stats.in_progress == 0
    assert stats.scheduled == 0


@pytest.mark.asyncio
async def test_cancel_task_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotFoundError):
        await service.cancel_task(999, user_id=1)


@pytest.mark.asyncio
async def test_cancel_completed_task(mock_task: Task) -> None:
    mock_task.status = TaskStatus.COMPLETED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotCancellableError):
        await service.cancel_task(1, user_id=1)


# --- edit_task tests ---


@pytest.mark.asyncio
async def test_edit_task_success(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Edit a pending task's phone number."""
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37399999999")
    result = await service.edit_task(1, user_id=1, data=data)

    assert result.target_phone == "+37399999999"
    mock_task_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_edit_task_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37399999999")

    with pytest.raises(TaskNotFoundError):
        await service.edit_task(999, user_id=1, data=data)


@pytest.mark.asyncio
async def test_edit_task_not_editable_in_progress(mock_task: Task) -> None:
    mock_task.status = TaskStatus.IN_PROGRESS
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37399999999")

    with pytest.raises(TaskNotEditableError):
        await service.edit_task(1, user_id=1, data=data)


@pytest.mark.asyncio
async def test_edit_task_not_editable_completed(mock_task: Task) -> None:
    mock_task.status = TaskStatus.COMPLETED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37399999999")

    with pytest.raises(TaskNotEditableError):
        await service.edit_task(1, user_id=1, data=data)


@pytest.mark.asyncio
async def test_edit_task_not_editable_failed(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37399999999")

    with pytest.raises(TaskNotEditableError):
        await service.edit_task(1, user_id=1, data=data)


@pytest.mark.asyncio
async def test_edit_task_update_slot_data(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Updating slot_data validates against template required_slots."""
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(slot_data={"preferred_date": "2026-04-01", "preferred_time": "14:00"})
    result = await service.edit_task(1, user_id=1, data=data)

    assert result.slot_data == {"preferred_date": "2026-04-01", "preferred_time": "14:00"}


@pytest.mark.asyncio
async def test_edit_task_missing_required_slots(mock_task: Task, mock_template: DialogTemplate) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(slot_data={"preferred_date": "2026-04-01"})

    with pytest.raises(InvalidTaskDataError, match="Missing required slots"):
        await service.edit_task(1, user_id=1, data=data)


@pytest.mark.asyncio
async def test_edit_task_set_scheduled_time_flips_status_to_scheduled(mock_task: Task) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    future_time = (datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    data = TaskEditRequest(scheduled_time=future_time.isoformat())

    result = await service.edit_task(1, user_id=1, data=data)

    assert result.status == TaskStatus.SCHEDULED
    assert result.scheduled_time is not None


@pytest.mark.asyncio
async def test_edit_task_admin_uses_any_user_lookup(mock_task: Task) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id_any_user = AsyncMock(return_value=mock_task)
    mock_task_repo.get_by_id = AsyncMock()
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskEditRequest(target_phone="+37360000000")

    await service.edit_task(task_id=1, user_id=99, data=data, is_admin=True)

    mock_task_repo.get_by_id_any_user.assert_awaited_once_with(1)
    mock_task_repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_get_task_admin_uses_any_user_lookup(mock_task: Task) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id_any_user = AsyncMock(return_value=mock_task)
    mock_task_repo.get_by_id = AsyncMock()
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.get_task(task_id=1, user_id=99, is_admin=True)

    assert result is mock_task
    mock_task_repo.get_by_id_any_user.assert_awaited_once_with(1)
    mock_task_repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_task_admin_uses_any_user_lookup(mock_task: Task) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id_any_user = AsyncMock(return_value=mock_task)
    mock_task_repo.get_by_id = AsyncMock()
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    await service.cancel_task(task_id=1, user_id=99, is_admin=True)

    mock_task_repo.get_by_id_any_user.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_retry_task_success(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_task.error_reason = "network error"
    mock_task.summary = "old summary"

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_task_repo._session = MagicMock()
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with patch("app.modules.calls.repository.CallSessionRepository") as mock_session_repo_cls, \
         patch("app.modules.calls.repository.LogLineRepository") as mock_line_repo_cls:
        mock_session_repo = mock_session_repo_cls.return_value
        mock_session_repo.get_by_task_id = AsyncMock(return_value=None)
        mock_line_repo_cls.return_value = MagicMock()

        result = await service.retry_task(task_id=1, user_id=1)

    assert result.status == TaskStatus.PENDING
    assert result.error_reason is None
    assert result.summary is None


@pytest.mark.asyncio
async def test_retry_task_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotFoundError):
        await service.retry_task(task_id=999, user_id=1)


@pytest.mark.asyncio
async def test_retry_task_not_failed_raises(mock_task: Task) -> None:
    mock_task.status = TaskStatus.COMPLETED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(InvalidTaskDataError, match="Only failed tasks"):
        await service.retry_task(task_id=1, user_id=1)


@pytest.mark.asyncio
async def test_retry_task_cleans_up_existing_call_session(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_existing_session = MagicMock()
    mock_existing_session.id = 42

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_task_repo._session = MagicMock()
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with patch("app.modules.calls.repository.CallSessionRepository") as mock_session_repo_cls, \
         patch("app.modules.calls.repository.LogLineRepository") as mock_line_repo_cls:
        mock_session_repo = mock_session_repo_cls.return_value
        mock_session_repo.get_by_task_id = AsyncMock(return_value=mock_existing_session)
        mock_session_repo.delete = AsyncMock()
        mock_line_repo = mock_line_repo_cls.return_value
        mock_line_repo.delete_by_session_id = AsyncMock()

        await service.retry_task(task_id=1, user_id=1)

        mock_line_repo.delete_by_session_id.assert_awaited_once_with(42)
        mock_session_repo.delete.assert_awaited_once_with(mock_existing_session)


@pytest.mark.asyncio
async def test_retry_task_admin_uses_any_user_lookup(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id_any_user = AsyncMock(return_value=mock_task)
    mock_task_repo.get_by_id = AsyncMock()
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_task_repo._session = MagicMock()
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with patch("app.modules.calls.repository.CallSessionRepository") as mock_session_repo_cls, \
         patch("app.modules.calls.repository.LogLineRepository"):
        mock_session_repo = mock_session_repo_cls.return_value
        mock_session_repo.get_by_task_id = AsyncMock(return_value=None)

        await service.retry_task(task_id=1, user_id=99, is_admin=True)

    mock_task_repo.get_by_id_any_user.assert_awaited_once_with(1)
    mock_task_repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_create_task_rejected_when_phone_rate_limit_exceeded(mock_template: DialogTemplate) -> None:
    from app.modules.tasks.exceptions import PhoneRateLimitExceededError

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_by_phone_in_last_24h = AsyncMock(return_value=3)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={"preferred_date": "2026-03-20", "preferred_time": "10:00"},
    )

    with patch("app.core.config.settings.MAX_CALLS_PER_PHONE_PER_DAY", 3), \
         pytest.raises(PhoneRateLimitExceededError, match="3 calls"):
        await service.create_task(data, user_id=1)


@pytest.mark.asyncio
async def test_create_task_allowed_below_rate_limit(mock_task: Task, mock_template: DialogTemplate) -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.create = AsyncMock(return_value=mock_task)
    mock_task_repo.count_by_phone_in_last_24h = AsyncMock(return_value=2)
    mock_task_repo.count_by_user_in_last_24h = AsyncMock(return_value=0)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    data = TaskCreate(
        target_phone="+37312345678",
        template_id=1,
        slot_data={"preferred_date": "2026-03-20", "preferred_time": "10:00"},
    )

    with patch("app.core.config.settings.MAX_CALLS_PER_PHONE_PER_DAY", 3):
        result = await service.create_task(data, user_id=1)

    assert result is mock_task


@pytest.mark.asyncio
async def test_rate_task_success(mock_task: Task) -> None:
    mock_task.status = TaskStatus.COMPLETED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.rate_task(task_id=1, user_id=1, rating=5, comment="Great")

    assert result is mock_task
    assert mock_task.user_rating == 5
    assert mock_task.user_rating_comment == "Great"


@pytest.mark.asyncio
async def test_rate_task_not_found() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotFoundError):
        await service.rate_task(task_id=999, user_id=1, rating=4, comment=None)


@pytest.mark.asyncio
async def test_rate_task_rejects_pending_status(mock_task: Task) -> None:
    mock_task.status = TaskStatus.PENDING
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(InvalidTaskDataError, match="completed or failed"):
        await service.rate_task(task_id=1, user_id=1, rating=5, comment=None)


@pytest.mark.asyncio
async def test_rate_task_admin_can_rate_any_user_task(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id_any_user = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.rate_task(task_id=1, user_id=99, rating=2, comment="Bad", is_admin=True)

    assert result is mock_task
    mock_task_repo.get_by_id_any_user.assert_called_once_with(1)
    mock_task_repo.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_rate_task_failed_status_succeeds(mock_task: Task) -> None:
    """Non-admin users can rate their own FAILED tasks."""
    mock_task.status = TaskStatus.FAILED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.rate_task(task_id=1, user_id=1, rating=3, comment="Didn't pick up")

    assert result is mock_task
    assert mock_task.user_rating == 3
    assert mock_task.user_rating_comment == "Didn't pick up"


@pytest.mark.asyncio
async def test_rate_task_without_comment_succeeds(mock_task: Task) -> None:
    """Rating without a comment (comment=None) should work."""
    mock_task.status = TaskStatus.COMPLETED
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=mock_task)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)
    result = await service.rate_task(task_id=1, user_id=1, rating=4, comment=None)

    assert result is mock_task
    assert mock_task.user_rating == 4
    assert mock_task.user_rating_comment is None


@pytest.mark.asyncio
async def test_rate_task_other_user_raises_not_found() -> None:
    """Non-admin rating a task owned by another user must raise TaskNotFoundError
    (user-scoped get_by_id returns None)."""
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_by_id = AsyncMock(return_value=None)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    service = TaskService(task_repository=mock_task_repo, template_repository=mock_template_repo)

    with pytest.raises(TaskNotFoundError):
        await service.rate_task(task_id=1, user_id=42, rating=5, comment="good")

    mock_task_repo.get_by_id.assert_awaited_once_with(1, 42)
    mock_task_repo.get_by_id_any_user.assert_not_called()
