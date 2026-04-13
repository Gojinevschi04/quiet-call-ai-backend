from collections.abc import Sequence

from sqlmodel import func, select

from app.core.repositories import Repository
from app.modules.audit.models import AuditLog


class AuditLogRepository(Repository):
    async def create(self, entry: AuditLog) -> AuditLog:
        self._session.add(entry)
        await self._session.commit()
        await self._session.refresh(entry)
        return entry

    async def get_all_paginated(
        self, limit: int = 50, offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.exec(query)
        items = result.all()

        count_result = await self._session.exec(select(func.count()).select_from(AuditLog))
        total = count_result.one()
        return items, total
