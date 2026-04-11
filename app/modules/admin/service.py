from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends
from sqlmodel import func, select

from app.core.logging import get_logger
from app.modules.calls.models import CallSession, LogLine
from app.modules.calls.repository import CallSessionRepository
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import AdminStatsResponse, TaskStatsResponse, TaskStatus
from app.modules.templates.models import DialogTemplate
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserRole

logger = get_logger(__name__)


class AdminService:
    def __init__(
        self,
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
        task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
        call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
    ) -> None:
        self.user_repository = user_repository
        self.task_repository = task_repository
        self.call_session_repository = call_session_repository

    async def get_system_stats(self) -> AdminStatsResponse:
        total_users = await self.user_repository.count()
        total_tasks = await self.task_repository.count_total()
        counts = await self.task_repository.count_by_status_all()
        total_calls = await self.call_session_repository.count_total()

        tasks_by_status = TaskStatsResponse(
            total=total_tasks,
            pending=counts.get(TaskStatus.PENDING, 0),
            scheduled=counts.get(TaskStatus.SCHEDULED, 0),
            in_progress=counts.get(TaskStatus.IN_PROGRESS, 0),
            completed=counts.get(TaskStatus.COMPLETED, 0),
            failed=counts.get(TaskStatus.FAILED, 0),
        )

        return AdminStatsResponse(
            total_users=total_users,
            total_tasks=total_tasks,
            tasks_by_status=tasks_by_status,
            total_calls=total_calls,
        )

    async def get_extended_stats(self) -> dict:
        session = self.user_repository._session

        # Tasks per template
        result = await session.exec(
            select(DialogTemplate.name, func.count(Task.id))
            .join(Task, Task.template_id == DialogTemplate.id)
            .group_by(DialogTemplate.name)
            .order_by(func.count(Task.id).desc())
        )
        tasks_per_template = [{"name": name, "count": count} for name, count in result.all()]

        # Average call duration
        result = await session.exec(
            select(func.avg(CallSession.duration)).where(CallSession.duration.is_not(None))
        )
        average_duration = round(result.one() or 0)

        # Tasks per day (last 30 days)
        result = await session.exec(
            select(
                func.date_trunc("day", Task.created_at).label("day"),
                func.count(Task.id),
            )
            .group_by("day")
            .order_by("day")
            .limit(30)
        )
        tasks_per_day = [{"date": str(day.date()), "count": count} for day, count in result.all()]

        # Users per month
        result = await session.exec(
            select(
                func.date_trunc("month", User.created_at).label("month"),
                func.count(User.id),
            )
            .group_by("month")
            .order_by("month")
        )
        users_per_month = [{"date": str(month.date()), "count": count} for month, count in result.all()]

        # Success rate per template — only templates with at least one terminal task count.
        result = await session.exec(
            select(
                DialogTemplate.name,
                func.count(Task.id),
                func.count(Task.id).filter(Task.status == TaskStatus.COMPLETED),
            )
            .join(Task, Task.template_id == DialogTemplate.id)
            .where(Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]))
            .group_by(DialogTemplate.name)
            .order_by(func.count(Task.id).desc())
        )
        success_rate_per_template = [
            {
                "name": name,
                "total": total,
                "completed": completed,
                "success_rate": round((completed / total) * 100, 1) if total else 0.0,
            }
            for name, total, completed in result.all()
        ]

        return {
            "tasks_per_template": tasks_per_template,
            "average_call_duration": average_duration,
            "tasks_per_day": tasks_per_day,
            "users_per_month": users_per_month,
            "success_rate_per_template": success_rate_per_template,
        }

    async def get_all_users(self, limit: int = 50, offset: int = 0) -> tuple[Sequence[User], int]:
        return await self.user_repository.get_all_paginated(offset, limit)

    async def get_all_tasks(
        self, limit: int = 50, offset: int = 0, status: TaskStatus | None = None
    ) -> tuple[Sequence[Task], int]:
        return await self.task_repository.get_all_paginated_admin(limit, offset, status)

    async def update_user_role(self, user_id: int, role: UserRole) -> User | None:
        return await self.user_repository.update_user_role(user_id, role)

    async def delete_user(self, user_id: int) -> bool:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return False

        # TODO: production — move cascade delete into a dedicated repository method
        # (e.g., UserRepository.delete_with_cascade) to avoid accessing _session directly.
        # Accessing the private _session breaks encapsulation but is acceptable for MVP.
        session = self.user_repository._session

        result = await session.exec(select(Task.id).where(Task.user_id == user_id))
        task_ids = list(result.all())

        if task_ids:
            result = await session.exec(select(CallSession.id).where(CallSession.task_id.in_(task_ids)))
            session_ids = list(result.all())

            if session_ids:
                result = await session.exec(select(LogLine).where(LogLine.session_id.in_(session_ids)))
                for log_line in result.all():
                    await session.delete(log_line)

                result = await session.exec(select(CallSession).where(CallSession.task_id.in_(task_ids)))
                for cs in result.all():
                    await session.delete(cs)

            result = await session.exec(select(Task).where(Task.user_id == user_id))
            for task in result.all():
                await session.delete(task)

        await session.delete(user)
        await session.commit()

        logger.info("Deleted user %d and %d associated tasks", user_id, len(task_ids))
        return True
