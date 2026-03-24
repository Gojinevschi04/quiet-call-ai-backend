from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.modules.tasks.exceptions import (
    InvalidTaskDataError,
    TaskNotCancellableError,
    TaskNotEditableError,
    TaskNotFoundError,
)
from app.modules.tasks.schema import TaskStatsResponse, TaskStatus
from app.modules.templates.exceptions import TemplateNotFoundError


@pytest.mark.asyncio
async def test_create_task(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.create_task") as mock_create:
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.target_phone = "+37312345678"
        mock_task.status = TaskStatus.PENDING
        mock_task.template_id = 1
        mock_task.slot_data = {"preferred_date": "2026-03-20"}
        mock_task.scheduled_time = None
        mock_task.summary = None
        mock_task.error_reason = None
        mock_task.created_at = "2026-01-01T00:00:00"
        mock_task.updated_at = "2026-01-01T00:00:00"
        mock_create.return_value = mock_task

        response = await authenticated_client.post(
            "/tasks/",
            json={"target_phone": "+37312345678", "template_id": 1, "slot_data": {"preferred_date": "2026-03-20"}},
        )
        assert response.status_code == 201
        assert response.json()["target_phone"] == "+37312345678"
        assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_create_task_template_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.create_task") as mock_create:
        mock_create.side_effect = TemplateNotFoundError("Not found")
        response = await authenticated_client.post(
            "/tasks/",
            json={"target_phone": "+37312345678", "template_id": 999, "slot_data": {}},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tasks(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_tasks") as mock_get:
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.target_phone = "+37312345678"
        mock_task.status = TaskStatus.PENDING
        mock_task.template_id = 1
        mock_task.slot_data = {}
        mock_task.scheduled_time = None
        mock_task.summary = None
        mock_task.error_reason = None
        mock_task.created_at = "2026-01-01T00:00:00"
        mock_task.updated_at = "2026-01-01T00:00:00"
        mock_get.return_value = ([mock_task], 1)

        response = await authenticated_client.get("/tasks/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_tasks_with_status_filter(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_tasks") as mock_get:
        mock_get.return_value = ([], 0)
        response = await authenticated_client.get("/tasks/?status=completed")
        assert response.status_code == 200
        assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_task_stats(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_stats") as mock_stats:
        mock_stats.return_value = TaskStatsResponse(total=10, pending=2, completed=5, failed=3)
        response = await authenticated_client.get("/tasks/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert data["completed"] == 5


@pytest.mark.asyncio
async def test_get_task(authenticated_client: AsyncClient) -> None:
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.target_phone = "+37312345678"
    mock_task.status = TaskStatus.COMPLETED
    mock_task.template_id = 1
    mock_task.slot_data = {}
    mock_task.scheduled_time = None
    mock_task.summary = "Appointment confirmed for March 20"
    mock_task.error_reason = None
    mock_task.created_at = "2026-01-01T00:00:00"
    mock_task.updated_at = "2026-01-01T00:00:00"

    mock_template = MagicMock()
    mock_template.name = "Make appointment"

    with (
        patch("app.modules.tasks.service.TaskService.get_task", new_callable=AsyncMock) as mock_get,
        patch("app.modules.templates.repository.TemplateRepository.get_by_id", new_callable=AsyncMock) as mock_tmpl,
    ):
        mock_get.return_value = mock_task
        mock_tmpl.return_value = mock_template

        response = await authenticated_client.get("/tasks/1")
        assert response.status_code == 200
        assert response.json()["summary"] == "Appointment confirmed for March 20"
        assert response.json()["template_name"] == "Make appointment"


@pytest.mark.asyncio
async def test_get_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_task") as mock_get:
        mock_get.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.get("/tasks/999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_task(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.cancel_task") as mock_cancel:
        mock_task = MagicMock()
        mock_task.status = TaskStatus.FAILED
        mock_cancel.return_value = mock_task
        response = await authenticated_client.post("/tasks/1/cancel")
        assert response.status_code == 200
        assert response.json()["message"] == "Task cancelled successfully"


@pytest.mark.asyncio
async def test_cancel_task_not_cancellable(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.cancel_task") as mock_cancel:
        mock_cancel.side_effect = TaskNotCancellableError("Cannot cancel")
        response = await authenticated_client.post("/tasks/1/cancel")
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_execute_task(authenticated_client: AsyncClient) -> None:
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.target_phone = "+37312345678"
    mock_task.status = TaskStatus.PENDING
    mock_task.template_id = 1
    mock_task.user_id = 1
    mock_task.slot_data = {}
    mock_task.scheduled_time = None
    mock_task.summary = None
    mock_task.error_reason = None
    mock_task.created_at = "2026-01-01T00:00:00"
    mock_task.updated_at = "2026-01-01T00:00:00"

    with (
        patch("app.modules.tasks.service.TaskService.get_task", new_callable=AsyncMock) as mock_get,
        patch("app.modules.tasks.views._run_call_in_background", new_callable=AsyncMock),
    ):
        mock_get.return_value = mock_task

        response = await authenticated_client.post("/tasks/1/execute")
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_execute_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_task", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = TaskNotFoundError("Task with id 999 not found")
        response = await authenticated_client.post("/tasks/999/execute")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_tasks_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_task_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/tasks/",
        json={"target_phone": "+37312345678", "template_id": 1, "slot_data": {}},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_task_stats_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_execute_completed_task(authenticated_client: AsyncClient) -> None:
    mock_task = MagicMock()
    mock_task.status = TaskStatus.COMPLETED

    with patch("app.modules.tasks.service.TaskService.get_task", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_task
        response = await authenticated_client.post("/tasks/1/execute")
        assert response.status_code == 409
        assert "cannot be executed" in response.json()["detail"]


# --- Validation edge cases ---


@pytest.mark.asyncio
async def test_create_task_invalid_phone(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/tasks/",
        json={"target_phone": "123", "template_id": 1, "slot_data": {}},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_missing_fields(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post("/tasks/", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_invalid_limit(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/tasks/?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_tasks_limit_too_high(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/tasks/?limit=101")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cancel_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.cancel_task") as mock_cancel:
        mock_cancel.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.post("/tasks/999/cancel")
        assert response.status_code == 404


# --- InvalidTaskDataError path ---


@pytest.mark.asyncio
async def test_create_task_invalid_data(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.create_task") as mock_create:
        mock_create.side_effect = InvalidTaskDataError("Missing required slot: preferred_date")
        response = await authenticated_client.post(
            "/tasks/",
            json={"target_phone": "+37312345678", "template_id": 1, "slot_data": {}},
        )
        assert response.status_code == 400
        assert "preferred_date" in response.json()["detail"]


# --- Slot data validation ---


@pytest.mark.asyncio
async def test_create_task_slot_key_too_long(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/tasks/",
        json={
            "target_phone": "+37312345678",
            "template_id": 1,
            "slot_data": {"k" * 51: "value"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_slot_value_too_long(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/tasks/",
        json={
            "target_phone": "+37312345678",
            "template_id": 1,
            "slot_data": {"key": "v" * 501},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_too_many_slots(authenticated_client: AsyncClient) -> None:
    slots = {f"slot_{i}": f"value_{i}" for i in range(21)}
    response = await authenticated_client.post(
        "/tasks/",
        json={"target_phone": "+37312345678", "template_id": 1, "slot_data": slots},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_invalid_status_filter(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/tasks/?status=nonexistent")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_negative_offset(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/tasks/?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cancel_task_unauthenticated(client: AsyncClient) -> None:
    response = await client.post("/tasks/1/cancel")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_execute_task_unauthenticated(client: AsyncClient) -> None:
    response = await client.post("/tasks/1/execute")
    assert response.status_code == 401


# --- Edit task ---


@pytest.mark.asyncio
async def test_edit_task_success(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.edit_task") as mock_edit:
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.target_phone = "+37399999999"
        mock_task.status = TaskStatus.PENDING
        mock_task.template_id = 1
        mock_task.slot_data = {}
        mock_task.scheduled_time = None
        mock_task.summary = None
        mock_task.error_reason = None
        mock_task.created_at = "2026-01-01T00:00:00"
        mock_task.updated_at = "2026-01-01T00:00:00"
        mock_edit.return_value = mock_task

        response = await authenticated_client.put("/tasks/1", json={"target_phone": "+37399999999"})
        assert response.status_code == 200
        assert response.json()["target_phone"] == "+37399999999"


@pytest.mark.asyncio
async def test_edit_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.edit_task") as mock_edit:
        mock_edit.side_effect = TaskNotFoundError("Not found")
        response = await authenticated_client.put("/tasks/999", json={"target_phone": "+37399999999"})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_edit_task_not_editable(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.edit_task") as mock_edit:
        mock_edit.side_effect = TaskNotEditableError("Cannot edit")
        response = await authenticated_client.put("/tasks/1", json={"target_phone": "+37399999999"})
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_edit_task_invalid_data(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.edit_task") as mock_edit:
        mock_edit.side_effect = InvalidTaskDataError("Missing required slots")
        response = await authenticated_client.put("/tasks/1", json={"slot_data": {}})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_edit_task_unauthenticated(client: AsyncClient) -> None:
    response = await client.put("/tasks/1", json={"target_phone": "+37399999999"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_scheduled_task_triggers_email_notification(authenticated_client: AsyncClient) -> None:
    from datetime import datetime, timedelta

    future_time = datetime.now() + timedelta(days=3)
    scheduled_task = MagicMock()
    scheduled_task.id = 1
    scheduled_task.target_phone = "+37312345678"
    scheduled_task.status = TaskStatus.SCHEDULED
    scheduled_task.template_id = 1
    scheduled_task.slot_data = {}
    scheduled_task.scheduled_time = future_time
    scheduled_task.summary = None
    scheduled_task.error_reason = None
    scheduled_task.created_at = future_time
    scheduled_task.updated_at = future_time

    template = MagicMock()
    template.language = "ro"

    with patch("app.modules.tasks.service.TaskService.create_task",
               new=AsyncMock(return_value=scheduled_task)), \
         patch("app.modules.templates.repository.TemplateRepository.get_by_id",
               new=AsyncMock(return_value=template)), \
         patch("app.modules.tasks.views.EmailService") as mock_email_service_cls:
        mock_email_service = mock_email_service_cls.return_value
        mock_email_service.send_task_scheduled = AsyncMock()

        response = await authenticated_client.post(
            "/tasks/",
            json={
                "target_phone": "+37312345678",
                "template_id": 1,
                "slot_data": {},
                "scheduled_time": future_time.isoformat(),
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_export_tasks_returns_csv(authenticated_client: AsyncClient) -> None:
    from datetime import datetime

    task_one = MagicMock()
    task_one.id = 1
    task_one.target_phone = "+37312345678"
    task_one.status = TaskStatus.COMPLETED
    task_one.template_id = 1
    task_one.scheduled_time = None
    task_one.summary = "Booked."
    task_one.error_reason = None
    task_one.created_at = datetime(2026, 4, 1, 10, 0)

    task_two = MagicMock()
    task_two.id = 2
    task_two.target_phone = "+37398765432"
    task_two.status = TaskStatus.FAILED
    task_two.template_id = 2
    task_two.scheduled_time = datetime(2026, 4, 5, 15, 0)
    task_two.summary = None
    task_two.error_reason = "No answer"
    task_two.created_at = datetime(2026, 4, 2, 11, 0)

    with patch("app.modules.tasks.service.TaskService.get_tasks",
               new=AsyncMock(return_value=([task_one, task_two], 2))):
        response = await authenticated_client.get("/tasks/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "tasks_export.csv" in response.headers["content-disposition"]

    csv_body = response.text
    assert "ID,Phone,Status,Template ID,Scheduled Time,Summary,Error,Created" in csv_body
    assert "+37312345678" in csv_body
    assert "No answer" in csv_body
    assert "Booked." in csv_body


@pytest.mark.asyncio
async def test_export_tasks_with_status_filter(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.get_tasks",
               new=AsyncMock(return_value=([], 0))) as mock_get_tasks:
        response = await authenticated_client.get("/tasks/export?status=failed")

    assert response.status_code == 200
    call_kwargs = mock_get_tasks.await_args.kwargs
    assert call_kwargs["status"] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_export_tasks_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/tasks/export")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_retry_task_success(authenticated_client: AsyncClient) -> None:
    retried_task = MagicMock()
    retried_task.id = 1
    retried_task.target_phone = "+37312345678"
    retried_task.status = TaskStatus.PENDING
    retried_task.template_id = 1
    retried_task.slot_data = {}
    retried_task.scheduled_time = None
    retried_task.summary = None
    retried_task.error_reason = None
    retried_task.created_at = "2026-01-01T00:00:00"
    retried_task.updated_at = "2026-01-01T00:00:00"

    with patch("app.modules.tasks.service.TaskService.retry_task",
               new=AsyncMock(return_value=retried_task)), \
         patch("app.modules.tasks.views._run_call_in_background", new=AsyncMock()):
        response = await authenticated_client.post("/tasks/1/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_retry_task_not_found(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.retry_task",
               new=AsyncMock(side_effect=TaskNotFoundError("missing"))):
        response = await authenticated_client.post("/tasks/999/retry")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_task_not_failed(authenticated_client: AsyncClient) -> None:
    with patch("app.modules.tasks.service.TaskService.retry_task",
               new=AsyncMock(side_effect=InvalidTaskDataError("Only failed tasks"))):
        response = await authenticated_client.post("/tasks/1/retry")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_retry_task_unauthenticated(client: AsyncClient) -> None:
    response = await client.post("/tasks/1/retry")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_run_call_in_background_uses_legacy_manager_when_flag_off() -> None:
    from app.modules.tasks.views import _run_call_in_background

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=None)

    with patch("app.modules.tasks.views.async_session") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.modules.tasks.views.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _run_call_in_background(task_id=1, user_id=2, is_admin=False)

    mock_manager.execute_task.assert_awaited_once_with(1, 2, is_admin=False)


@pytest.mark.asyncio
async def test_run_call_in_background_uses_realtime_manager_when_flag_on() -> None:
    from app.modules.tasks.views import _run_call_in_background

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(return_value=None)

    with patch("app.modules.tasks.views.async_session") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", True), \
         patch("app.modules.tasks.views.RealtimeCallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _run_call_in_background(task_id=3, user_id=4, is_admin=True)

    mock_manager.execute_task.assert_awaited_once_with(3, 4, is_admin=True)


@pytest.mark.asyncio
async def test_run_call_in_background_swallows_exceptions() -> None:
    from app.modules.tasks.views import _run_call_in_background

    mock_manager = MagicMock()
    mock_manager.execute_task = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("app.modules.tasks.views.async_session") as mock_session_cls, \
         patch("app.core.config.settings.USE_REALTIME_API", False), \
         patch("app.modules.tasks.views.CallManager", return_value=mock_manager):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _run_call_in_background(task_id=1, user_id=2, is_admin=False)
