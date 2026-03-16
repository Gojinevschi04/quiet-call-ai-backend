import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.logging import get_logger
from app.core.schema import MessageResponse
from app.modules.auth.schema import LoginRequest, PasswordResetRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.notifications.email_service import EmailService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    user_repository: Annotated[UserRepository, Depends(UserRepository)],
) -> TokenResponse:
    existing_user = await user_repository.get_by_email(data.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    hashed_password = AuthService.hash_password(data.password)
    user = User(email=data.email, role=UserRole.USER, hashed_password=hashed_password, phone_number=data.phone_number)
    created_user = await user_repository.create(user)
    # Send welcome email in background (don't block registration)
    asyncio.create_task(EmailService().send_welcome(created_user.email))
    return AuthService.create_tokens(created_user.id)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> TokenResponse:
    user = await auth_service.authenticate_user(data.email, data.password)
    return AuthService.create_tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
) -> TokenResponse:
    return AuthService.refresh_access_token(data.refresh_token)


@router.post("/reset-password")
async def reset_password(
    data: PasswordResetRequest,
    user_repository: Annotated[UserRepository, Depends(UserRepository)],
) -> MessageResponse:
    # Always return success to not reveal if email exists (security best practice)
    user = await user_repository.get_by_email(data.email)
    if user:
        reset_token = AuthService.create_reset_token(user.id)
        asyncio.create_task(EmailService().send_password_reset(user.email, reset_token))
    return MessageResponse(message="If an account with that email exists, a reset link has been sent")
