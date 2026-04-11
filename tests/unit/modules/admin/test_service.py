from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.admin.service import AdminService
from app.modules.calls.repository import CallSessionRepository
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserRole


def _build_service(
    user_repo: MagicMock | None = None,
    task_repo: MagicMock | None = None,
    call_repo: MagicMock | None = None,
) -> AdminService:
    return AdminService(
        user_repository=user_repo or MagicMock(spec=UserRepository),
        task_repository=task_repo or MagicMock(spec=TaskRepository),
        call_session_repository=call_repo or MagicMock(spec=CallSessionRepository),
    )


# --- get_system_stats ---


@pytest.mark.asyncio
async def test_get_system_stats() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.count = AsyncMock(return_value=15)

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_total = AsyncMock(return_value=100)
    mock_task_repo.count_by_status_all = AsyncMock(
        return_value={
            TaskStatus.PENDING: 10,
            TaskStatus.COMPLETED: 70,
            TaskStatus.FAILED: 15,
            TaskStatus.IN_PROGRESS: 5,
        }
    )

    mock_call_repo = MagicMock(spec=CallSessionRepository)
    mock_call_repo.count_total = AsyncMock(return_value=85)

    service = _build_service(mock_user_repo, mock_task_repo, mock_call_repo)
    stats = await service.get_system_stats()

    assert stats.total_users == 15
    assert stats.total_tasks == 100
    assert stats.total_calls == 85
    assert stats.tasks_by_status.completed == 70
    assert stats.tasks_by_status.failed == 15
    assert stats.tasks_by_status.pending == 10
    assert stats.tasks_by_status.scheduled == 0


@pytest.mark.asyncio
async def test_get_system_stats_empty() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.count = AsyncMock(return_value=0)

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_total = AsyncMock(return_value=0)
    mock_task_repo.count_by_status_all = AsyncMock(return_value={})

    mock_call_repo = MagicMock(spec=CallSessionRepository)
    mock_call_repo.count_total = AsyncMock(return_value=0)

    service = _build_service(mock_user_repo, mock_task_repo, mock_call_repo)
    stats = await service.get_system_stats()

    assert stats.total_users == 0
    assert stats.total_tasks == 0
    assert stats.total_calls == 0
    assert stats.tasks_by_status.total == 0


@pytest.mark.asyncio
async def test_get_system_stats_all_statuses_present() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.count = AsyncMock(return_value=5)

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.count_total = AsyncMock(return_value=25)
    mock_task_repo.count_by_status_all = AsyncMock(
        return_value={
            TaskStatus.PENDING: 5,
            TaskStatus.SCHEDULED: 3,
            TaskStatus.IN_PROGRESS: 2,
            TaskStatus.COMPLETED: 10,
            TaskStatus.FAILED: 5,
        }
    )

    mock_call_repo = MagicMock(spec=CallSessionRepository)
    mock_call_repo.count_total = AsyncMock(return_value=12)

    service = _build_service(mock_user_repo, mock_task_repo, mock_call_repo)
    stats = await service.get_system_stats()

    assert stats.tasks_by_status.pending == 5
    assert stats.tasks_by_status.scheduled == 3
    assert stats.tasks_by_status.in_progress == 2
    assert stats.tasks_by_status.completed == 10
    assert stats.tasks_by_status.failed == 5


# --- get_all_users ---


@pytest.mark.asyncio
async def test_get_all_users() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_users = [MagicMock(spec=User), MagicMock(spec=User)]
    mock_user_repo.get_all_paginated = AsyncMock(return_value=(mock_users, 2))

    service = _build_service(user_repo=mock_user_repo)
    users, total = await service.get_all_users(limit=50, offset=0)

    assert total == 2
    assert len(users) == 2
    mock_user_repo.get_all_paginated.assert_called_once_with(0, 50)


@pytest.mark.asyncio
async def test_get_all_users_empty() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_all_paginated = AsyncMock(return_value=([], 0))

    service = _build_service(user_repo=mock_user_repo)
    users, total = await service.get_all_users()

    assert total == 0
    assert len(users) == 0


@pytest.mark.asyncio
async def test_get_all_users_custom_pagination() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_all_paginated = AsyncMock(return_value=([], 10))

    service = _build_service(user_repo=mock_user_repo)
    users, total = await service.get_all_users(limit=5, offset=5)

    assert total == 10
    mock_user_repo.get_all_paginated.assert_called_once_with(5, 5)


# --- get_all_tasks ---


@pytest.mark.asyncio
async def test_get_all_tasks() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_tasks = [MagicMock(spec=Task)]
    mock_task_repo.get_all_paginated_admin = AsyncMock(return_value=(mock_tasks, 1))

    service = _build_service(task_repo=mock_task_repo)
    tasks, total = await service.get_all_tasks(limit=50, offset=0)

    assert total == 1
    assert len(tasks) == 1
    mock_task_repo.get_all_paginated_admin.assert_called_once_with(50, 0, None)


@pytest.mark.asyncio
async def test_get_all_tasks_with_status_filter() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_all_paginated_admin = AsyncMock(return_value=([], 0))

    service = _build_service(task_repo=mock_task_repo)
    tasks, total = await service.get_all_tasks(limit=10, offset=0, status=TaskStatus.FAILED)

    assert total == 0
    mock_task_repo.get_all_paginated_admin.assert_called_once_with(10, 0, TaskStatus.FAILED)


@pytest.mark.asyncio
async def test_get_all_tasks_custom_pagination() -> None:
    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.get_all_paginated_admin = AsyncMock(return_value=([], 50))

    service = _build_service(task_repo=mock_task_repo)
    tasks, total = await service.get_all_tasks(limit=20, offset=30)

    assert total == 50
    mock_task_repo.get_all_paginated_admin.assert_called_once_with(20, 30, None)


# --- update_user_role ---


@pytest.mark.asyncio
async def test_update_user_role() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user = MagicMock(spec=User)
    mock_user.role = UserRole.ADMIN
    mock_user_repo.update_user_role = AsyncMock(return_value=mock_user)

    service = _build_service(user_repo=mock_user_repo)
    result = await service.update_user_role(1, UserRole.ADMIN)

    assert result is not None
    assert result.role == UserRole.ADMIN
    mock_user_repo.update_user_role.assert_called_once_with(1, UserRole.ADMIN)


@pytest.mark.asyncio
async def test_update_user_role_not_found() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.update_user_role = AsyncMock(return_value=None)

    service = _build_service(user_repo=mock_user_repo)
    result = await service.update_user_role(999, UserRole.ADMIN)

    assert result is None


@pytest.mark.asyncio
async def test_update_user_role_demote_to_user() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user = MagicMock(spec=User)
    mock_user.role = UserRole.USER
    mock_user_repo.update_user_role = AsyncMock(return_value=mock_user)

    service = _build_service(user_repo=mock_user_repo)
    result = await service.update_user_role(1, UserRole.USER)

    assert result is not None
    assert result.role == UserRole.USER


# --- delete_user ---


@pytest.mark.asyncio
async def test_delete_user(mock_user: User) -> None:
    mock_session = AsyncMock()
    # No tasks for user
    mock_result_empty = MagicMock()
    mock_result_empty.all.return_value = []
    mock_session.exec = AsyncMock(return_value=mock_result_empty)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo._session = mock_session

    service = _build_service(user_repo=mock_user_repo)
    result = await service.delete_user(1)

    assert result is True
    mock_session.delete.assert_called_once_with(mock_user)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user_not_found() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)

    service = _build_service(user_repo=mock_user_repo)
    result = await service.delete_user(999)

    assert result is False


@pytest.mark.asyncio
async def test_delete_user_cascades_tasks_sessions_and_log_lines(mock_user: User) -> None:
    """User with tasks + call sessions + log lines is fully cascade-deleted."""
    mock_task_ids_result = MagicMock()
    mock_task_ids_result.all.return_value = [10, 11]
    mock_session_ids_result = MagicMock()
    mock_session_ids_result.all.return_value = [100]
    mock_log_line = MagicMock()
    mock_log_lines_result = MagicMock()
    mock_log_lines_result.all.return_value = [mock_log_line]
    mock_call_session = MagicMock()
    mock_call_sessions_result = MagicMock()
    mock_call_sessions_result.all.return_value = [mock_call_session]
    mock_task = MagicMock()
    mock_tasks_result = MagicMock()
    mock_tasks_result.all.return_value = [mock_task]

    mock_session = AsyncMock()
    mock_session.exec = AsyncMock(side_effect=[
        mock_task_ids_result,
        mock_session_ids_result,
        mock_log_lines_result,
        mock_call_sessions_result,
        mock_tasks_result,
    ])
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo._session = mock_session

    service = _build_service(user_repo=mock_user_repo)
    result = await service.delete_user(1)

    assert result is True
    assert mock_session.delete.await_count == 4
    mock_session.delete.assert_any_await(mock_log_line)
    mock_session.delete.assert_any_await(mock_call_session)
    mock_session.delete.assert_any_await(mock_task)
    mock_session.delete.assert_any_await(mock_user)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_with_tasks_but_no_sessions(mock_user: User) -> None:
    mock_task_ids_result = MagicMock()
    mock_task_ids_result.all.return_value = [10]
    mock_empty_sessions_result = MagicMock()
    mock_empty_sessions_result.all.return_value = []
    mock_task = MagicMock()
    mock_tasks_result = MagicMock()
    mock_tasks_result.all.return_value = [mock_task]

    mock_session = AsyncMock()
    mock_session.exec = AsyncMock(side_effect=[
        mock_task_ids_result,
        mock_empty_sessions_result,
        mock_tasks_result,
    ])
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo._session = mock_session

    service = _build_service(user_repo=mock_user_repo)
    result = await service.delete_user(1)

    assert result is True
    assert mock_session.delete.await_count == 2


@pytest.mark.asyncio
async def test_get_extended_stats_assembles_all_four_sections() -> None:
    from datetime import datetime

    template_result = MagicMock()
    template_result.all.return_value = [("Make appointment", 15), ("Confirm reservation", 7)]

    duration_result = MagicMock()
    duration_result.one.return_value = 65.4

    day_one = datetime(2026, 4, 1)
    day_two = datetime(2026, 4, 2)
    tasks_per_day_result = MagicMock()
    tasks_per_day_result.all.return_value = [(day_one, 3), (day_two, 5)]

    month_one = datetime(2026, 1, 1)
    users_per_month_result = MagicMock()
    users_per_month_result.all.return_value = [(month_one, 4)]

    success_rate_result = MagicMock()
    success_rate_result.all.return_value = [
        ("Make appointment", 10, 8),
        ("Confirm reservation", 5, 5),
    ]

    mock_session = AsyncMock()
    mock_session.exec = AsyncMock(side_effect=[
        template_result,
        duration_result,
        tasks_per_day_result,
        users_per_month_result,
        success_rate_result,
    ])

    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo._session = mock_session

    service = _build_service(user_repo=mock_user_repo)
    stats = await service.get_extended_stats()

    assert stats["tasks_per_template"] == [
        {"name": "Make appointment", "count": 15},
        {"name": "Confirm reservation", "count": 7},
    ]
    assert stats["average_call_duration"] == 65
    assert stats["tasks_per_day"] == [
        {"date": "2026-04-01", "count": 3},
        {"date": "2026-04-02", "count": 5},
    ]
    assert stats["users_per_month"] == [{"date": "2026-01-01", "count": 4}]
    assert stats["success_rate_per_template"] == [
        {"name": "Make appointment", "total": 10, "completed": 8, "success_rate": 80.0},
        {"name": "Confirm reservation", "total": 5, "completed": 5, "success_rate": 100.0},
    ]


@pytest.mark.asyncio
async def test_get_extended_stats_average_duration_is_zero_when_no_calls() -> None:
    empty_result = MagicMock()
    empty_result.all.return_value = []

    duration_result = MagicMock()
    duration_result.one.return_value = None

    mock_session = AsyncMock()
    mock_session.exec = AsyncMock(side_effect=[
        empty_result,
        duration_result,
        empty_result,
        empty_result,
        empty_result,
    ])

    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo._session = mock_session

    service = _build_service(user_repo=mock_user_repo)
    stats = await service.get_extended_stats()

    assert stats["average_call_duration"] == 0
    assert stats["tasks_per_template"] == []
    assert stats["tasks_per_day"] == []
    assert stats["users_per_month"] == []
    assert stats["success_rate_per_template"] == []
