from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlmodel import func, select

from app.core.logging import get_logger
from app.modules.admin.exceptions import UserHasActiveCallError
from app.modules.calls.models import CallSession
from app.modules.calls.pricing import (
    COST_DECIMAL_PLACES,
    SECONDS_PER_MINUTE,
    estimate_cost_usd,
    estimate_twilio_cost_usd,
)
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
            deferred=counts.get(TaskStatus.DEFERRED, 0),
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
        result = await session.exec(select(func.avg(CallSession.duration)).where(CallSession.duration.is_not(None)))
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
            .where(Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.DEFERRED]))
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

    async def get_cost_breakdown(self) -> dict:
        """Per-user + totals cost breakdown for the current calendar month.

        Returns Twilio + OpenAI estimated USD cost per user, total minutes, and
        the aggregate $/min across all calls.
        """
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        rows = await self.call_session_repository.get_monthly_usage_per_user(month_start)

        per_user_breakdown = []
        total_duration_seconds = 0
        total_cost_usd = 0.0
        for row in rows:
            (
                user_id,
                email,
                call_count,
                duration_seconds,
                input_audio_tokens,
                output_audio_tokens,
                input_text_tokens,
                output_text_tokens,
            ) = row
            duration_seconds = int(duration_seconds or 0)
            input_audio_tokens = int(input_audio_tokens or 0)
            output_audio_tokens = int(output_audio_tokens or 0)
            input_text_tokens = int(input_text_tokens or 0)
            output_text_tokens = int(output_text_tokens or 0)
            twilio_cost = estimate_twilio_cost_usd(duration_seconds)
            openai_cost = estimate_cost_usd(
                input_audio_tokens, output_audio_tokens, input_text_tokens, output_text_tokens
            )
            entry_total_cost = round(twilio_cost + openai_cost, COST_DECIMAL_PLACES)
            per_user_breakdown.append(
                {
                    "user_id": user_id,
                    "email": email,
                    "call_count": int(call_count),
                    "duration_seconds": duration_seconds,
                    "twilio_cost_usd": twilio_cost,
                    "openai_cost_usd": openai_cost,
                    "total_cost_usd": entry_total_cost,
                }
            )
            total_duration_seconds += duration_seconds
            total_cost_usd += entry_total_cost

        total_minutes = total_duration_seconds / SECONDS_PER_MINUTE if total_duration_seconds else 0
        avg_cost_per_min_usd = round(total_cost_usd / total_minutes, COST_DECIMAL_PLACES) if total_minutes else 0.0
        return {
            "period_start": month_start.isoformat(),
            "per_user": per_user_breakdown,
            "total_cost_usd": round(total_cost_usd, COST_DECIMAL_PLACES),
            "total_minutes": round(total_minutes, 2),
            "avg_cost_per_min_usd": avg_cost_per_min_usd,
        }

    async def get_all_users(self, limit: int = 50, offset: int = 0) -> tuple[Sequence[User], int]:
        return await self.user_repository.get_all_paginated(offset, limit)

    async def get_all_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
        status: TaskStatus | None = None,
        language: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> tuple[Sequence[Task], int]:
        return await self.task_repository.get_all_paginated_admin(limit, offset, status, language, sort_by, sort_dir)

    async def update_user_role(self, user_id: int, role: UserRole) -> User | None:
        return await self.user_repository.update_user_role(user_id, role)

    async def delete_user(self, user_id: int) -> bool:
        """Soft-delete: set `is_active=False`. Keeps audit trail + historical tasks.

        Rejects when the user has an IN_PROGRESS task — we don't want to silently
        orphan a live call. Admin should wait for the call to finish or cancel it first.
        """
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return False

        session = self.user_repository._session
        in_progress_result = await session.exec(
            select(Task.id).where(Task.user_id == user_id, Task.status == TaskStatus.IN_PROGRESS)
        )
        if in_progress_result.first() is not None:
            raise UserHasActiveCallError(
                f"User {user_id} has an in-progress call. Wait for it to finish or cancel it first."
            )

        user.is_active = False
        session.add(user)
        await session.commit()
        logger.info("Soft-deleted user %d (is_active=False)", user_id)
        return True

    async def restore_user(self, user_id: int) -> bool:
        """Re-activate a soft-deleted user."""
        user = await self.user_repository.get_by_id(user_id)
        if not user or user.is_active:
            return False
        user.is_active = True
        self.user_repository._session.add(user)
        await self.user_repository._session.commit()
        logger.info("Restored user %d (is_active=True)", user_id)
        return True
