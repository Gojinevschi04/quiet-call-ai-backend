import asyncio
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.schema import MessageResponse
from app.integrations.call_manager import CallManager
from app.modules.notifications.email_service import EmailService
from app.modules.tasks.exceptions import (
    InvalidTaskDataError,
    TaskNotCancellableError,
    TaskNotEditableError,
    TaskNotFoundError,
)
from app.modules.tasks.schema import (
    TaskCreate,
    TaskEditRequest,
    TaskListResponse,
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
        task = await task_service.create_task(data, current_user.id)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except InvalidTaskDataError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e

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
        items=[_task_to_response(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
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
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    try:
        is_admin = current_user.role == UserRole.ADMIN
        task = await task_service.get_task(task_id, current_user.id, is_admin=is_admin)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e

    return _task_to_response(task)


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

    return _task_to_response(task)


@router.post("/{task_id}/cancel")
async def cancel_task_view(
    task_id: int,
    task_service: Annotated[TaskService, Depends(TaskService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    try:
        await task_service.cancel_task(task_id, current_user.id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except TaskNotCancellableError as e:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(e)) from e

    return MessageResponse(message="Task cancelled successfully")


@router.post("/{task_id}/execute")
async def execute_task_view(
    task_id: int,
    call_manager: Annotated[CallManager, Depends(CallManager)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TaskResponse:
    try:
        task = await call_manager.execute_task(task_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e

    return _task_to_response(task)
