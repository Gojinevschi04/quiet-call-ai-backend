import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.schema import MessageResponse
from app.core.utils import get_request_language
from app.modules.notifications.email_service import EmailService
from app.modules.users.middleware import get_current_admin_user, get_current_user
from app.modules.users.models import User
from app.modules.users.schema import (
    ChangePassword,
    ProfileUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_profile_view(
    user_service: Annotated[UserService, Depends(UserService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return await user_service.get_profile(current_user.id)


@router.put("/me")
async def update_profile_view(
    request: Request,
    data: ProfileUpdate,
    user_service: Annotated[UserService, Depends(UserService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse | MessageResponse:
    try:
        profile = await user_service.update_profile(current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if data.email is not None and data.email != current_user.email:
        lang = get_request_language(request)
        asyncio.create_task(EmailService().send_email_changed(current_user.email, data.email, language=lang))
        return MessageResponse(
            message="Profile updated. Please log in again with your new email.",
            require_reauth=True,
        )
    return profile


@router.post("/me/change-password")
async def change_password_view(
    request: Request,
    data: ChangePassword,
    user_service: Annotated[UserService, Depends(UserService)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    try:
        await user_service.change_password(current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lang = get_request_language(request)
    asyncio.create_task(EmailService().send_password_changed(current_user.email, language=lang))
    return MessageResponse(message="Password changed successfully", require_reauth=True)


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    user_service: Annotated[UserService, Depends(UserService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    try:
        return await user_service.create_user(user_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=UserListResponse)
async def get_users(
    user_service: Annotated[UserService, Depends(UserService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
    skip: int = 0,
    limit: int = 100,
) -> UserListResponse:
    return await user_service.get_users(skip, limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    user_service: Annotated[UserService, Depends(UserService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    user_service: Annotated[UserService, Depends(UserService)],
    _current_user: Annotated[User, Depends(get_current_admin_user)],
) -> UserResponse:
    try:
        user = await user_service.update_user(user_id, user_data)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    user_service: Annotated[UserService, Depends(UserService)],
    current_user: Annotated[User, Depends(get_current_admin_user)],
) -> MessageResponse:
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return MessageResponse(message="User deleted successfully")
