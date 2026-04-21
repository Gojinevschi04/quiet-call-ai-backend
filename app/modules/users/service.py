from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.core.logging import get_logger
from app.modules.auth.service import AuthService
from app.modules.calls.pricing import estimate_cost_usd
from app.modules.calls.repository import CallSessionRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import (
    ChangePassword,
    ProfileUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRole,
    UserUpdate,
    UserUsageResponse,
)

logger = get_logger(__name__)


class UserService:
    def __init__(
        self,
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
        call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
    ) -> None:
        self.user_repository = user_repository
        self.call_session_repository = call_session_repository

    async def get_usage(self, user_id: int) -> UserUsageResponse:
        totals = await self.call_session_repository.get_usage_for_user(user_id)
        estimated_cost = estimate_cost_usd(
            totals["input_audio_tokens"],
            totals["output_audio_tokens"],
            totals["input_text_tokens"],
            totals["output_text_tokens"],
        )
        return UserUsageResponse(
            call_count=totals["call_count"],
            input_audio_tokens=totals["input_audio_tokens"],
            output_audio_tokens=totals["output_audio_tokens"],
            input_text_tokens=totals["input_text_tokens"],
            output_text_tokens=totals["output_text_tokens"],
            estimated_cost_usd=estimated_cost,
        )

    def _to_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            phone_number=user.phone_number,
            email_notifications=user.email_notifications,
            webhook_url=user.webhook_url,
            assistant_name=user.assistant_name,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        existing_user = await self.user_repository.get_by_email(user_data.email)
        if existing_user:
            raise ValueError("User with this email already exists")

        hashed_password = AuthService.hash_password(user_data.password)
        user = User(
            email=user_data.email,
            role=UserRole.USER,
            hashed_password=hashed_password,
            phone_number=user_data.phone_number,
        )
        created_user = await self.user_repository.create(user)
        return self._to_response(created_user)

    async def update_user(self, user_id: int, user_data: UserUpdate) -> UserResponse | None:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None

        if user_data.email is not None:
            existing_user = await self.user_repository.get_by_email(user_data.email)
            if existing_user and existing_user.id != user_id:
                raise ValueError("User with this email already exists")
            user.email = user_data.email

        if user_data.role is not None:
            user.role = user_data.role

        if user_data.phone_number is not None:
            user.phone_number = user_data.phone_number

        updated_user = await self.user_repository.update(user)
        return self._to_response(updated_user)

    async def delete_user(self, user_id: int) -> bool:
        return await self.user_repository.delete(user_id)

    async def get_user(self, user_id: int) -> UserResponse | None:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None
        return self._to_response(user)

    async def get_users(self, skip: int = 0, limit: int = 100) -> UserListResponse:
        users, total = await self.user_repository.get_all_paginated(skip, limit)
        user_responses = [self._to_response(user) for user in users]
        return UserListResponse(users=user_responses, total=total, skip=skip, limit=limit)

    async def get_profile(self, user_id: int) -> UserResponse:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return self._to_response(user)

    async def update_profile(self, user_id: int, data: ProfileUpdate) -> UserResponse:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if data.email is not None:
            existing = await self.user_repository.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise ValueError("User with this email already exists")
            user.email = data.email

        if data.phone_number is not None:
            user.phone_number = data.phone_number

        if data.email_notifications is not None:
            user.email_notifications = data.email_notifications

        if data.webhook_url is not None:
            user.webhook_url = data.webhook_url or None

        if data.assistant_name is not None:
            user.assistant_name = data.assistant_name or None

        updated_user = await self.user_repository.update(user)
        return self._to_response(updated_user)

    async def change_password(self, user_id: int, data: ChangePassword) -> bool:
        user = await self.user_repository.get_by_id(user_id)
        if not user or not user.hashed_password:
            raise ValueError("User not found")

        if not AuthService.verify_password(data.current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = AuthService.hash_password(data.new_password)
        user.password_changed_at = datetime.now(UTC).replace(tzinfo=None)
        await self.user_repository.update(user)
        return True
