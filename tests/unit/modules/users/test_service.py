from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.auth.service import AuthService
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
)
from app.modules.users.service import UserService


@pytest.mark.asyncio
async def test_create_user_success(mock_session: MagicMock) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)
    new_user = User(id=1, email="new@example.com", role=UserRole.USER)
    mock_user_repo.create = AsyncMock(return_value=new_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    user_data = UserCreate(email="new@example.com", role=UserRole.USER, password="testpass123")
    result = await service.create_user(user_data)

    assert isinstance(result, UserResponse)
    assert result.email == "new@example.com"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(mock_session: MagicMock, mock_user: User) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    user_data = UserCreate(email="test@example.com", role=UserRole.USER, password="testpass123")
    with pytest.raises(ValueError):
        await service.create_user(user_data)


@pytest.mark.asyncio
async def test_update_user_success(mock_session: MagicMock, mock_user: User) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)
    updated_user = User(id=1, email="updated@example.com", role=UserRole.ADMIN)
    mock_user_repo.update = AsyncMock(return_value=updated_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    user_data = UserUpdate(email="updated@example.com", role=UserRole.ADMIN)
    result = await service.update_user(1, user_data)

    assert isinstance(result, UserResponse)
    assert result.email == "updated@example.com"


@pytest.mark.asyncio
async def test_update_user_not_found(mock_session: MagicMock) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    user_data = UserUpdate(email="updated@example.com")
    result = await service.update_user(999, user_data)

    assert result is None


@pytest.mark.asyncio
async def test_delete_user_success(mock_session: MagicMock) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.delete = AsyncMock(return_value=True)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    result = await service.delete_user(1)

    assert result is True


@pytest.mark.asyncio
async def test_get_user_success(mock_session: MagicMock, mock_user: User) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    result = await service.get_user(1)

    assert isinstance(result, UserResponse)
    assert result.id == mock_user.id


@pytest.mark.asyncio
async def test_get_user_not_found(mock_session: MagicMock) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    result = await service.get_user(999)

    assert result is None


@pytest.mark.asyncio
async def test_get_users(mock_session: MagicMock) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    users = [User(id=i, email=f"user{i}@example.com") for i in range(3)]
    mock_user_repo.get_all_paginated = AsyncMock(return_value=(users, 3))

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    result = await service.get_users(skip=0, limit=100)

    assert isinstance(result, UserListResponse)
    assert result.total == 3


# --- get_profile ---


@pytest.mark.asyncio
async def test_get_profile_success(mock_user: User) -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    result = await service.get_profile(1)

    assert isinstance(result, UserResponse)
    assert result.id == mock_user.id
    assert result.email == mock_user.email


@pytest.mark.asyncio
async def test_get_profile_not_found() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    with pytest.raises(ValueError, match="User not found"):
        await service.get_profile(999)


# --- update_profile ---


@pytest.mark.asyncio
async def test_update_profile_success(mock_user: User) -> None:
    updated_user = User(
        id=1,
        email="new@example.com",
        role=UserRole.USER,
        created_at=mock_user.created_at,
        updated_at=mock_user.updated_at,
    )
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)
    mock_user_repo.update = AsyncMock(return_value=updated_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ProfileUpdate(email="new@example.com")
    result = await service.update_profile(1, data)

    assert isinstance(result, UserResponse)
    assert result.email == "new@example.com"


@pytest.mark.asyncio
async def test_update_profile_email_change(mock_user: User) -> None:
    updated_user = User(
        id=1,
        email="changed@example.com",
        role=UserRole.USER,
        created_at=mock_user.created_at,
        updated_at=mock_user.updated_at,
    )
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)
    mock_user_repo.update = AsyncMock(return_value=updated_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ProfileUpdate(email="changed@example.com")
    result = await service.update_profile(1, data)

    assert result.email == "changed@example.com"
    mock_user_repo.get_by_email.assert_called_once_with("changed@example.com")


@pytest.mark.asyncio
async def test_update_profile_duplicate_email(mock_user: User) -> None:
    other_user = User(id=99, email="taken@example.com", role=UserRole.USER)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.get_by_email = AsyncMock(return_value=other_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ProfileUpdate(email="taken@example.com")
    with pytest.raises(ValueError, match="already exists"):
        await service.update_profile(1, data)


@pytest.mark.asyncio
async def test_update_profile_phone_only(mock_user: User) -> None:
    updated_user = User(
        id=1,
        email="test@example.com",
        role=UserRole.USER,
        phone_number="+37399999999",
        created_at=mock_user.created_at,
        updated_at=mock_user.updated_at,
    )
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.update = AsyncMock(return_value=updated_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ProfileUpdate(phone_number="+37399999999")
    result = await service.update_profile(1, data)

    assert result.phone_number == "+37399999999"
    mock_user_repo.get_by_email.assert_not_called()


# --- change_password ---


@pytest.mark.asyncio
async def test_change_password_success(mock_user: User) -> None:
    mock_user.hashed_password = AuthService.hash_password("oldpassword")
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_user_repo.update = AsyncMock(return_value=mock_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ChangePassword(current_password="oldpassword", new_password="newpassword123")
    result = await service.change_password(1, data)

    assert result is True
    mock_user_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_change_password_wrong_current(mock_user: User) -> None:
    mock_user.hashed_password = AuthService.hash_password("correct_password")
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ChangePassword(current_password="wrong_password", new_password="newpassword123")
    with pytest.raises(ValueError, match="Current password is incorrect"):
        await service.change_password(1, data)


@pytest.mark.asyncio
async def test_change_password_user_not_found() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)

    service = UserService(user_repository=mock_user_repo, call_session_repository=MagicMock(spec=CallSessionRepository))
    data = ChangePassword(current_password="oldpass", new_password="newpassword123")
    with pytest.raises(ValueError, match="User not found"):
        await service.change_password(999, data)


@pytest.mark.asyncio
async def test_get_usage_returns_aggregated_cost() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_usage_for_user = AsyncMock(
        return_value={
            "input_audio_tokens": 1_000_000,
            "output_audio_tokens": 1_000_000,
            "input_text_tokens": 1_000_000,
            "output_text_tokens": 1_000_000,
            "call_count": 7,
            "duration_seconds": 600,
        }
    )

    service = UserService(user_repository=mock_user_repo, call_session_repository=mock_call_session_repo)
    response = await service.get_usage(user_id=1)

    assert response.call_count == 7
    assert response.input_audio_tokens == 1_000_000
    assert response.output_audio_tokens == 1_000_000
    assert response.input_text_tokens == 1_000_000
    assert response.output_text_tokens == 1_000_000
    assert response.duration_seconds == 600
    assert response.openai_cost_usd == 32.0 + 64.0 + 4.0 + 16.0
    # 600 sec = 10 min × ($0.30 + $0.004) = $3.04
    assert response.twilio_cost_usd == pytest.approx(3.04, abs=0.001)
    assert response.estimated_cost_usd == pytest.approx(116.0 + 3.04, abs=0.001)


@pytest.mark.asyncio
async def test_get_usage_zero_calls_returns_zero_cost() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_usage_for_user = AsyncMock(
        return_value={
            "input_audio_tokens": 0,
            "output_audio_tokens": 0,
            "input_text_tokens": 0,
            "output_text_tokens": 0,
            "call_count": 0,
            "duration_seconds": 0,
        }
    )

    service = UserService(user_repository=mock_user_repo, call_session_repository=mock_call_session_repo)
    response = await service.get_usage(user_id=42)

    assert response.call_count == 0
    assert response.estimated_cost_usd == 0.0
    assert response.twilio_cost_usd == 0.0
    assert response.openai_cost_usd == 0.0
