from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.scheduler.service import (
    MAX_IN_PROGRESS_MINUTES,
    _process_due_tasks,
    _process_retryable_tasks,
    _process_stuck_in_progress_tasks,
    get_due_tasks,
    get_retryable_failed_tasks,
    mark_task_for_retry,
    transition_task,
)
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus


@pytest.mark.asyncio
async def test_get_due_tasks_returns_scheduled() -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = [(1, 10)]  # (task_id, user_id)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)

    tasks = await get_due_tasks(mock_session)

    assert len(tasks) == 1
    assert tasks[0] == (1, 10)


@pytest.mark.asyncio
async def test_get_due_tasks_empty() -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)

    tasks = await get_due_tasks(mock_session)

    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_transition_task_scheduled_to_pending() -> None:
    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.SCHEDULED,
        template_id=1,
        user_id=1,
        slot_data={},
        scheduled_time=datetime.now() - timedelta(hours=1),
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await transition_task(mock_session, 1)

    assert task.status == TaskStatus.PENDING
    mock_session.add.assert_called_once_with(task)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_transition_task_not_found() -> None:
    mock_result = MagicMock()
    mock_result.first.return_value = None

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await transition_task(mock_session, 999)

    # Should not commit if task not found
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_transition_task_already_pending() -> None:
    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.PENDING,
        template_id=1,
        user_id=1,
        slot_data={},
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await transition_task(mock_session, 1)

    # Should not transition if already PENDING
    assert task.status == TaskStatus.PENDING
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_retryable_failed_tasks_network_error() -> None:
    from app.modules.scheduler.service import MAX_RETRY_ATTEMPTS

    mock_result = MagicMock()
    mock_result.all.return_value = [
        (1, 10, "Connection refused after 3 retries", 0, None),
        (2, 11, "Cancelled by user", 0, None),
        (3, 12, "timeout connecting to Twilio", 1, datetime.now() - timedelta(minutes=1)),
        (4, 13, "Connection refused", MAX_RETRY_ATTEMPTS, None),
        (5, 14, "network error", 1, datetime.now() + timedelta(minutes=10)),
    ]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)

    tasks = await get_retryable_failed_tasks(mock_session)

    assert len(tasks) == 2
    assert (1, 10) in tasks
    assert (3, 12) in tasks


@pytest.mark.asyncio
async def test_get_retryable_failed_tasks_empty() -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)

    tasks = await get_retryable_failed_tasks(mock_session)
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_mark_task_for_retry() -> None:
    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="Connection refused",
        retry_count=0,
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await mark_task_for_retry(mock_session, 1)

    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 1
    assert task.next_retry_at is None
    assert task.summary is None
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_task_for_retry_not_failed() -> None:
    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.COMPLETED,
        template_id=1,
        user_id=1,
        slot_data={},
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await mark_task_for_retry(mock_session, 1)

    assert task.status == TaskStatus.COMPLETED
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_process_stuck_in_progress_tasks_flips_old_tasks_to_failed() -> None:
    stuck_cutoff_time = datetime.now() - timedelta(minutes=MAX_IN_PROGRESS_MINUTES + 1)
    stuck_task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.IN_PROGRESS,
        template_id=1,
        user_id=1,
        slot_data={},
        updated_at=stuck_cutoff_time,
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [stuck_task]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.modules.scheduler.service.async_session") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_stuck_in_progress_tasks()

    assert stuck_task.status == TaskStatus.FAILED
    assert "Stuck at IN_PROGRESS" in stuck_task.error_reason
    mock_session.add.assert_called_once_with(stuck_task)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_stuck_in_progress_tasks_no_stuck_does_nothing() -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.modules.scheduler.service.async_session") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_stuck_in_progress_tasks()

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_process_stuck_in_progress_tasks_preserves_existing_error_reason() -> None:
    stuck_task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.IN_PROGRESS,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="original reason",
        updated_at=datetime.now() - timedelta(minutes=MAX_IN_PROGRESS_MINUTES + 5),
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [stuck_task]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.modules.scheduler.service.async_session") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_stuck_in_progress_tasks()

    assert stuck_task.error_reason == "original reason"
    assert stuck_task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_process_due_tasks_transitions_and_executes_each() -> None:
    due_tasks_result = MagicMock()
    due_tasks_result.all.return_value = [(1, 10), (2, 20)]

    transition_result = MagicMock()
    transition_result.first.return_value = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.SCHEDULED,
        template_id=1,
        user_id=10,
        slot_data={},
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(side_effect=[due_tasks_result, transition_result, transition_result])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.modules.scheduler.service.async_session") as mock_session_cls,
        patch("app.modules.scheduler.task_executor.execute_due_task") as mock_execute,
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_execute.return_value = AsyncMock()
        mock_execute.side_effect = [None, None]

        await _process_due_tasks()

    assert mock_execute.await_count == 2


@pytest.mark.asyncio
async def test_process_due_tasks_swallows_per_task_errors() -> None:
    due_tasks_result = MagicMock()
    due_tasks_result.all.return_value = [(1, 10), (2, 20)]

    transition_result = MagicMock()
    transition_result.first.return_value = None

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=due_tasks_result)
    mock_session.commit = AsyncMock()

    async def _fail_execute(task_id: int, user_id: int) -> None:
        raise RuntimeError(f"boom {task_id}")

    with (
        patch("app.modules.scheduler.service.async_session") as mock_session_cls,
        patch("app.modules.scheduler.task_executor.execute_due_task", new=_fail_execute),
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_due_tasks()


@pytest.mark.asyncio
async def test_process_retryable_tasks_resets_and_executes() -> None:
    new_retry_window_result = MagicMock()
    new_retry_window_result.all.return_value = []

    retryable_result = MagicMock()
    retryable_result.all.return_value = [
        (5, 50, "Connection refused after 3 retries", 0, datetime.now() - timedelta(minutes=2)),
    ]

    mark_result = MagicMock()
    mark_result.first.return_value = Task(
        id=5,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=50,
        slot_data={},
        error_reason="Connection refused",
        retry_count=0,
    )

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(side_effect=[new_retry_window_result, retryable_result, mark_result])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with (
        patch("app.modules.scheduler.service.async_session") as mock_session_cls,
        patch("app.modules.scheduler.task_executor.execute_due_task", new=AsyncMock()) as mock_execute,
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_retryable_tasks()

    mock_execute.assert_awaited_once_with(5, 50)


@pytest.mark.asyncio
async def test_process_retryable_tasks_empty_is_noop() -> None:
    empty_result = MagicMock()
    empty_result.all.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=empty_result)

    with (
        patch("app.modules.scheduler.service.async_session") as mock_session_cls,
        patch("app.modules.scheduler.task_executor.execute_due_task", new=AsyncMock()) as mock_execute,
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _process_retryable_tasks()

    mock_execute.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_next_retry_uses_backoff_for_first_attempt() -> None:
    from app.modules.scheduler.service import RETRY_BACKOFF_MINUTES, schedule_next_retry

    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="Connection refused",
        retry_count=0,
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    before = datetime.now()
    await schedule_next_retry(mock_session, 1)
    after = datetime.now()

    assert task.next_retry_at is not None
    expected_min = before + timedelta(minutes=RETRY_BACKOFF_MINUTES[0])
    expected_max = after + timedelta(minutes=RETRY_BACKOFF_MINUTES[0])
    assert expected_min <= task.next_retry_at <= expected_max


@pytest.mark.asyncio
async def test_schedule_next_retry_uses_longer_backoff_for_later_attempts() -> None:
    from app.modules.scheduler.service import RETRY_BACKOFF_MINUTES, schedule_next_retry

    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="network error",
        retry_count=2,
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    before = datetime.now()
    await schedule_next_retry(mock_session, 1)

    assert task.next_retry_at is not None
    gap = task.next_retry_at - before
    assert abs(gap.total_seconds() - RETRY_BACKOFF_MINUTES[2] * 60) < 5


@pytest.mark.asyncio
async def test_schedule_next_retry_clears_window_after_max_attempts() -> None:
    from app.modules.scheduler.service import MAX_RETRY_ATTEMPTS, schedule_next_retry

    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="timeout",
        retry_count=MAX_RETRY_ATTEMPTS,
        next_retry_at=datetime.now() + timedelta(minutes=30),
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await schedule_next_retry(mock_session, 1)

    assert task.next_retry_at is None


@pytest.mark.asyncio
async def test_schedule_next_retry_noops_for_non_failed_task() -> None:
    from app.modules.scheduler.service import schedule_next_retry

    task = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.COMPLETED,
        template_id=1,
        user_id=1,
        slot_data={},
    )

    mock_result = MagicMock()
    mock_result.first.return_value = task

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    await schedule_next_retry(mock_session, 1)

    assert task.next_retry_at is None
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_retryable_failed_tasks_skips_tasks_with_empty_error_reason() -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (1, 10, "", 0, None),
        (2, 11, None, 0, None),
        (3, 12, "Connection refused", 0, None),
    ]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=mock_result)

    tasks = await get_retryable_failed_tasks(mock_session)

    assert tasks == [(3, 12)]


@pytest.mark.asyncio
async def test_schedule_new_retry_windows_sets_next_retry_for_eligible_tasks() -> None:
    from app.modules.scheduler.service import _schedule_new_retry_windows

    fresh_failed_result = MagicMock()
    fresh_failed_result.all.return_value = [
        (1, "Connection refused", 0),
        (2, "Cancelled by user", 0),
    ]

    task_for_retry = Task(
        id=1,
        target_phone="+37312345678",
        status=TaskStatus.FAILED,
        template_id=1,
        user_id=1,
        slot_data={},
        error_reason="Connection refused",
        retry_count=0,
    )
    fetch_result = MagicMock()
    fetch_result.first.return_value = task_for_retry

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(side_effect=[fresh_failed_result, fetch_result])
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.modules.scheduler.service.async_session") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _schedule_new_retry_windows()

    assert task_for_retry.next_retry_at is not None


@pytest.mark.asyncio
async def test_schedule_new_retry_windows_skips_tasks_at_max_retries() -> None:
    from app.modules.scheduler.service import MAX_RETRY_ATTEMPTS, _schedule_new_retry_windows

    fresh_failed_result = MagicMock()
    fresh_failed_result.all.return_value = [
        (1, "Connection refused", MAX_RETRY_ATTEMPTS),
    ]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.exec = AsyncMock(return_value=fresh_failed_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch("app.modules.scheduler.service.async_session") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _schedule_new_retry_windows()

    mock_session.add.assert_not_called()
