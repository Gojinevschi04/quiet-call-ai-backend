from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.schema import MessageResponse
from app.modules.admin.service import AdminService
from app.modules.tasks.schema import AdminStatsResponse, TaskListResponse, TaskResponse, TaskStatus
from app.modules.users.middleware import get_current_admin_user
from app.modules.users.models import User
from app.modules.users.schema import UserListResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_admin_stats_view(
    admin_service: Annotated[AdminService, Depends(AdminService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> AdminStatsResponse:
    return await admin_service.get_system_stats()


@router.get("/stats/extended")
async def get_admin_extended_stats_view(
    admin_service: Annotated[AdminService, Depends(AdminService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> dict:
    return await admin_service.get_extended_stats()


@router.get("/stats/costs")
async def get_admin_cost_breakdown_view(
    admin_service: Annotated[AdminService, Depends(AdminService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> dict:
    return await admin_service.get_cost_breakdown()


@router.get("/users")
async def get_admin_users_view(
    admin_service: Annotated[AdminService, Depends(AdminService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    users, total = await admin_service.get_all_users(limit, offset)
    return UserListResponse(
        users=[
            UserResponse(
                id=u.id,
                email=u.email,
                role=u.role,
                phone_number=u.phone_number,
                created_at=u.created_at.isoformat(),
                updated_at=u.updated_at.isoformat(),
            )
            for u in users
        ],
        total=total,
        skip=offset,
        limit=limit,
    )


@router.get("/tasks")
async def get_admin_tasks_view(
    admin_service: Annotated[AdminService, Depends(AdminService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: TaskStatus | None = None,
) -> TaskListResponse:
    tasks, total = await admin_service.get_all_tasks(limit, offset, status)
    return TaskListResponse(
        items=[
            TaskResponse(
                id=t.id,
                target_phone=t.target_phone,
                status=t.status,
                template_id=t.template_id,
                user_id=t.user_id,
                slot_data=t.slot_data,
                scheduled_time=t.scheduled_time,
                summary=t.summary,
                error_reason=t.error_reason,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/users/{user_id}")
async def update_admin_user_role_view(
    user_id: int,
    data: UserUpdate,
    admin_service: Annotated[AdminService, Depends(AdminService)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    if user_id == current_user.id and data.role is not None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Cannot change your own role")

    if data.role is None:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Role is required")

    user = await admin_service.update_user_role(user_id, data.role)
    if not user:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="User not found")

    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        phone_number=user.phone_number,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.delete("/users/{user_id}")
async def delete_admin_user_view(
    user_id: int,
    admin_service: Annotated[AdminService, Depends(AdminService)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> MessageResponse:
    if user_id == current_user.id:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Cannot delete your own account")

    success = await admin_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="User not found")

    return MessageResponse(message="User deleted successfully")
