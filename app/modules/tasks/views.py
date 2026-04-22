import asyncio
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.concurrency import get_call_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.core.logging import get_logger
from app.core.schema import MessageResponse
from app.integrations.call_manager import CallManager
from app.integrations.realtime_call_manager import RealtimeCallManager
from app.modules.audit.service import record_audit
from app.modules.notifications.email_service import EmailService
from app.modules.tasks.exceptions import (
    InvalidTaskDataError,
    PhoneRateLimitExceededError,
    TaskNotCancellableError,
    TaskNotEditableError,
    TaskNotFoundError,
    UserDailyQuotaExceededError,
)
from app.modules.tasks.schema import (
    TaskCreate,
    TaskDuplicateRequest,
    TaskEditRequest,
    TaskListResponse,
    TaskRatingRequest,
    TaskResponse,
    TaskStatsResponse,
    TaskStatus,
)
from app.modules.tasks.service import TaskService
from app.modules.templates.exceptions import TemplateNotFoundError
from app.modules.templates.repository import TemplateRepository
from app.modules.users.middleware import get_current_user
from app.modules.users.models import User
from app.modules.users.schema import UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_to_response(task: "Task", template_name: str | None = None) -> TaskResponse:  # noqa: F821
    return TaskResponse(
        id=task.id,
        target_phone=task.target_phone,
        status=task.status,
        template_id=task.template_id,
        template_name=template_name,
        user_id=task.user_id,
        slot_data=task.slot_data,
        scheduled_time=task.scheduled_time,
        summary=task.summary,
        error_reason=task.error_reason,
        retry_count=task.retry_count,
        next_retry_at=task.next_retry_at,
        user_rating=task.user_rating,
        user_rating_comment=task.user_rating_comment,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/", status_code=HTTPStatus.CREATED)
async def create_task_view(
    data: TaskCreate,
    task_service: Annotated[TaskService, Depends(TaskService)],
    template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    try:
        task = await task_service.create_task(
            data,
            current_user.id,
            is_admin=current_user.role == UserRole.ADMIN,
        )
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    except (PhoneRateLimitExceededError, UserDailyQuotaExceededError) as e:
        raise HTTPException(status_code=HTTPStatus.TOO_MANY_REQUESTS, detail=str(e)) from e

    if task.scheduled_time:
        template = await template_repository.get_by_id(data.template_id)
        language = template.language if template else "en"
        asyncio.create_task(
            EmailService().send_task_scheduled(
                current_user.email,
                task.target_phone,
                task.scheduled_time.strftime("%Y-%m-%d %H:%M"),
                language=language,
            )
        )

    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.create",
            target_type="task",
            target_id=task.id,
            details=f"phone={task.target_phone} template_id={task.template_id}",
        )
    )
    return _task_to_response(task)


@router.get("/")
async def get_tasks_view(
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: TaskStatus | None = None,
) -> TaskListResponse:
    tasks, total = await task_service.get_tasks(current_user.id, limit, offset, status)
    return TaskListResponse(
        items=[_task_to_response(task) for task in tasks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export")
async def export_tasks_csv_view(
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: TaskStatus | None = None,
) -> StreamingResponse:
    import csv
    import io

    tasks, _total = await task_service.get_tasks(current_user.id, limit=1000, offset=0, status=status)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Phone", "Status", "Template ID", "Scheduled Time", "Summary", "Error", "Created"])
    for task in tasks:
        writer.writerow(
            [
                task.id,
                task.target_phone,
                task.status,
                task.template_id,
                task.scheduled_time.isoformat() if task.scheduled_time else "",
                task.summary or "",
                task.error_reason or "",
                task.created_at.isoformat(),
            ]
        )

    csv_bytes = output.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks_export.csv"},
    )


@router.get("/stats")
async def get_task_stats_view(
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskStatsResponse:
    return await task_service.get_stats(current_user.id)


@router.get("/{task_id}")
async def get_task_view(
    task_id: int,
    task_service: Annotated[TaskService, Depends(TaskService)],
    template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    try:
        is_admin = current_user.role == UserRole.ADMIN
        task = await task_service.get_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e

    template = await template_repository.get_by_id(task.template_id)
    template_name = template.name if template else None
    return _task_to_response(task, template_name=template_name)


@router.put("/{task_id}")
async def edit_task_view(
    task_id: int,
    data: TaskEditRequest,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    try:
        is_admin = current_user.role == UserRole.ADMIN
        task = await task_service.edit_task(task_id, current_user.id, data, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except TaskNotEditableError as e:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(e)) from e
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e

    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.edit",
            target_type="task",
            target_id=task_id,
        )
    )
    return _task_to_response(task)


@router.post("/{task_id}/cancel")
async def cancel_task_view(
    task_id: int,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    try:
        is_admin = current_user.role == UserRole.ADMIN
        await task_service.cancel_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except TaskNotCancellableError as e:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(e)) from e

    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.cancel",
            target_type="task",
            target_id=task_id,
        )
    )
    return MessageResponse(message="Task cancelled successfully")


@router.post("/{task_id}/rate")
async def rate_task_view(
    task_id: int,
    data: TaskRatingRequest,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    is_admin = current_user.role == UserRole.ADMIN
    try:
        task = await task_service.rate_task(
            task_id,
            current_user.id,
            data.rating,
            data.comment,
            is_admin=is_admin,
        )
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(e)) from e
    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.rate",
            target_type="task",
            target_id=task_id,
            details=f"rating={data.rating}",
        )
    )
    return _task_to_response(task)


@router.post("/{task_id}/duplicate", status_code=HTTPStatus.CREATED)
async def duplicate_task_view(
    task_id: int,
    data: TaskDuplicateRequest,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    """Clone an existing task's template + slot_data into a new task for a different phone."""
    is_admin = current_user.role == UserRole.ADMIN
    try:
        source = await task_service.get_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e

    new_task_data = TaskCreate(
        target_phone=data.target_phone,
        template_id=source.template_id,
        slot_data=dict(source.slot_data),
        scheduled_time=data.scheduled_time,
    )
    try:
        new_task = await task_service.create_task(
            new_task_data,
            current_user.id,
            is_admin=is_admin,
            allow_inactive_template=True,
        )
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    except (PhoneRateLimitExceededError, UserDailyQuotaExceededError) as e:
        raise HTTPException(status_code=HTTPStatus.TOO_MANY_REQUESTS, detail=str(e)) from e
    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.duplicate",
            target_type="task",
            target_id=new_task.id,
            details=f"source={task_id}",
        )
    )
    return _task_to_response(new_task)


@router.post("/{task_id}/retry")
async def retry_task_view(
    task_id: int,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    is_admin = current_user.role == UserRole.ADMIN
    try:
        task = await task_service.retry_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(e)) from e

    asyncio.create_task(_run_call_in_background(task_id, current_user.id, is_admin))
    task.status = TaskStatus.IN_PROGRESS
    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.retry",
            target_type="task",
            target_id=task_id,
        )
    )
    return _task_to_response(task)


async def _run_call_in_background(task_id: int, user_id: int, is_admin: bool) -> None:
    """Run call execution with its own DB session (not tied to the HTTP request).

    Gated by a process-local semaphore so we don't exceed MAX_CONCURRENT_CALLS.
    """
    from app.modules.calls.repository import CallSessionRepository, LogLineRepository
    from app.modules.tasks.repository import TaskRepository as TaskRepo
    from app.modules.templates.repository import TemplateRepository as TemplateRepo
    from app.modules.users.repository import UserRepository

    semaphore = get_call_semaphore()
    async with semaphore:
        try:
            async with async_session() as session:
                repos = {
                    "task_repository": TaskRepo(session=session),
                    "template_repository": TemplateRepo(session=session),
                    "call_session_repository": CallSessionRepository(session=session),
                    "log_line_repository": LogLineRepository(session=session),
                    "user_repository": UserRepository(session=session),
                }
                manager = RealtimeCallManager(**repos) if settings.USE_REALTIME_API else CallManager(**repos)
                await manager.execute_task(task_id, user_id, is_admin=is_admin)
        except Exception:
            logger.exception("Background call execution failed for task %d", task_id)


@router.post("/{task_id}/execute")
async def execute_task_view(
    task_id: int,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    is_admin = current_user.role == UserRole.ADMIN
    try:
        task = await task_service.get_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e

    if task.status not in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"Task with status '{task.status}' cannot be executed",
        )

    asyncio.create_task(_run_call_in_background(task_id, current_user.id, is_admin))
    task.status = TaskStatus.IN_PROGRESS
    asyncio.create_task(
        record_audit(
            user_id=current_user.id,
            action="task.execute",
            target_type="task",
            target_id=task_id,
        )
    )
    return _task_to_response(task)
