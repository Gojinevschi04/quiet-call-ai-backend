from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.tasks.exceptions import (
    InvalidTaskDataError,
    PhoneRateLimitExceededError,
    TaskNotCancellableError,
    TaskNotEditableError,
    TaskNotFoundError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskCreate, TaskEditRequest, TaskStatsResponse, TaskStatus
from app.modules.templates.exceptions import TemplateNotFoundError
from app.modules.templates.repository import TemplateRepository

logger = get_logger(__name__)


class TaskService:
    def __init__(
        self,
        task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
        template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
    ) -> None:
        self.task_repository = task_repository
        self.template_repository = template_repository

    async def create_task(self, data: TaskCreate, user_id: int) -> Task:
        template = await self.template_repository.get_by_id(data.template_id)
        if not template:
            raise TemplateNotFoundError(f"Template with id {data.template_id} not found")

        missing_slots = [slot for slot in template.required_slots if slot not in data.slot_data]
        if missing_slots:
            raise InvalidTaskDataError(f"Missing required slots: {', '.join(missing_slots)}")

        recent_count = await self.task_repository.count_by_phone_in_last_24h(data.target_phone)
        if recent_count >= settings.MAX_CALLS_PER_PHONE_PER_DAY:
            raise PhoneRateLimitExceededError(
                f"Phone {data.target_phone} already has {recent_count} calls in the last 24 hours "
                f"(limit: {settings.MAX_CALLS_PER_PHONE_PER_DAY}). Try again tomorrow."
            )

        status = TaskStatus.SCHEDULED if data.scheduled_time else TaskStatus.PENDING

        task = Task(
            target_phone=data.target_phone,
            status=status,
            template_id=data.template_id,
            user_id=user_id,
            slot_data=data.slot_data,
            scheduled_time=data.scheduled_time,
        )

        logger.info("Creating task for user %s with template %s", user_id, template.name)
        return await self.task_repository.create(task)

    async def get_task(self, task_id: int, user_id: int, is_admin: bool = False) -> Task:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")
        return task

    async def get_tasks(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        status: TaskStatus | None = None,
    ) -> tuple[Sequence[Task], int]:
        return await self.task_repository.get_all_paginated(user_id, limit, offset, status)

    async def edit_task(self, task_id: int, user_id: int, data: TaskEditRequest, is_admin: bool = False) -> Task:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")

        if task.status not in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
            raise TaskNotEditableError(
                f"Task with status '{task.status}' cannot be edited. Only pending or scheduled tasks can be modified."
            )

        if data.target_phone is not None:
            task.target_phone = data.target_phone

        if data.slot_data is not None:
            template = await self.template_repository.get_by_id(task.template_id)
            if template:
                missing_slots = [slot for slot in template.required_slots if slot not in data.slot_data]
                if missing_slots:
                    raise InvalidTaskDataError(f"Missing required slots: {', '.join(missing_slots)}")
            task.slot_data = data.slot_data

        if data.scheduled_time is not None:
            task.scheduled_time = data.scheduled_time
            task.status = TaskStatus.SCHEDULED
        elif "scheduled_time" in (data.model_fields_set or set()):
            task.scheduled_time = None
            task.status = TaskStatus.PENDING

        logger.info("Edited task %d by user %d", task_id, user_id)
        return await self.task_repository.update(task)

    async def cancel_task(self, task_id: int, user_id: int, is_admin: bool = False) -> Task:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")

        if task.status not in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
            raise TaskNotCancellableError(f"Task with status '{task.status}' cannot be cancelled")

        task.status = TaskStatus.FAILED
        task.error_reason = "Cancelled by user"
        return await self.task_repository.update(task)

    async def retry_task(self, task_id: int, user_id: int, is_admin: bool = False) -> Task:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")

        if task.status != TaskStatus.FAILED:
            raise InvalidTaskDataError(f"Only failed tasks can be retried (current status: {task.status})")

        await self._cleanup_old_call_session(task_id)

        task.status = TaskStatus.PENDING
        task.error_reason = None
        task.summary = None
        return await self.task_repository.update(task)

    async def _cleanup_old_call_session(self, task_id: int) -> None:
        from app.modules.calls.repository import CallSessionRepository, LogLineRepository

        session = self.task_repository._session
        call_session_repo = CallSessionRepository(session=session)
        log_line_repo = LogLineRepository(session=session)

        call_session = await call_session_repo.get_by_task_id(task_id)
        if not call_session:
            return

        await log_line_repo.delete_by_session_id(call_session.id)
        await call_session_repo.delete(call_session)

    async def get_stats(self, user_id: int) -> TaskStatsResponse:
        counts = await self.task_repository.count_by_status(user_id)
        return TaskStatsResponse(
            total=sum(counts.values()),
            pending=counts.get(TaskStatus.PENDING, 0),
            scheduled=counts.get(TaskStatus.SCHEDULED, 0),
            in_progress=counts.get(TaskStatus.IN_PROGRESS, 0),
            completed=counts.get(TaskStatus.COMPLETED, 0),
            failed=counts.get(TaskStatus.FAILED, 0),
        )
