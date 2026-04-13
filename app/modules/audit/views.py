from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.audit.schema import AuditLogListResponse, AuditLogResponse
from app.modules.audit.service import AuditService
from app.modules.users.middleware import get_current_admin_user
from app.modules.users.models import User

router = APIRouter(prefix="/admin/audit", tags=["admin"])


@router.get("/", status_code=HTTPStatus.OK)
async def list_audit_log_view(
    audit_service: Annotated[AuditService, Depends(AuditService)],
    _admin: Annotated[User, Depends(get_current_admin_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogListResponse:
    items, total = await audit_service.list_entries(limit, offset)
    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=entry.id,
                user_id=entry.user_id,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                details=entry.details,
                created_at=entry.created_at,
            )
            for entry in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
