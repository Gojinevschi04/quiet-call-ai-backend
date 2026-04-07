from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlmodel import func, select

from app.core.repositories import Repository
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus


class TaskRepository(Repository):
    async def create(self, task: Task) -> Task:
        self._session.add(task)
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def get_by_id(self, task_id: int, user_id: int) -> Task | None:
        result = await self._session.exec(select(Task).where(Task.id == task_id, Task.user_id == user_id))
        return result.first()

    async def get_by_id_any_user(self, task_id: int) -> Task | None:
        result = await self._session.exec(select(Task).where(Task.id == task_id))
        return result.first()

    async def get_all_paginated(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        status: TaskStatus | None = None,
    ) -> tuple[Sequence[Task], int]:
        query = select(Task).where(Task.user_id == user_id)
        count_query = select(func.count()).select_from(Task).where(Task.user_id == user_id)

        if status:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)

        result = await self._session.exec(query)
        tasks = result.all()

        count_result = await self._session.exec(count_query)
        total = count_result.one()

        return tasks, total

    async def update(self, task: Task) -> Task:
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def count_by_status(self, user_id: int) -> dict[str, int]:
        result = await self._session.exec(
            select(Task.status, func.count()).where(Task.user_id == user_id).group_by(Task.status)
        )
        counts: dict[str, int] = {}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def get_all_paginated_admin(
        self,
        limit: int = 50,
        offset: int = 0,
        status: TaskStatus | None = None,
    ) -> tuple[Sequence[Task], int]:
        query = select(Task)
        count_query = select(func.count()).select_from(Task)

        if status:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)

        query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)

        result = await self._session.exec(query)
        tasks = result.all()
        count_result = await self._session.exec(count_query)
        total = count_result.one()

        return tasks, total

    async def count_by_status_all(self) -> dict[str, int]:
        result = await self._session.exec(
            select(Task.status, func.count()).group_by(Task.status)
        )
        counts: dict[str, int] = {}
        for status, count in result.all():
            counts[status] = count
        return counts

    async def count_total(self) -> int:
        result = await self._session.exec(select(func.count()).select_from(Task))
        return result.one()

    async def count_by_phone_in_last_24h(self, target_phone: str) -> int:
        """Count tasks created for a given phone number in the last 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        result = await self._session.exec(
            select(func.count())
            .select_from(Task)
            .where(Task.target_phone == target_phone, Task.created_at >= cutoff)
        )
        return result.one()
