from collections.abc import Sequence
from typing import Annotated

from fastapi import Depends

from app.core.database import async_session
from app.core.logging import get_logger
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository

logger = get_logger(__name__)


class AuditService:
    def __init__(
        self,
        audit_repository: Annotated[AuditLogRepository, Depends(AuditLogRepository)],
    ) -> None:
        self.audit_repository = audit_repository

    async def list_entries(
        self, limit: int = 50, offset: int = 0,
    ) -> tuple[Sequence[AuditLog], int]:
        return await self.audit_repository.get_all_paginated(limit, offset)


async def record_audit(
    user_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None = None,
    details: str | None = None,
) -> None:
    """Fire-and-forget audit recording using a dedicated DB session.

    Safe to call from anywhere — swallows DB errors so audit failures never
    break the primary request path.
    """
    try:
        async with async_session() as session:
            repo = AuditLogRepository(session=session)
            entry = AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
            await repo.create(entry)
    except Exception:
        logger.exception("Failed to record audit log entry (user=%s action=%s)", user_id, action)
