from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.modules.auth.auth_handler import decode_token
from app.modules.auth.schema import TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

# --- hash_password / verify_password (real bcrypt, no mocking) ---


@pytest.mark.asyncio
async def test_hash_password_returns_string() -> None:
    hashed = AuthService.hash_password("mysecretpass")
    assert isinstance(hashed, str)
    assert hashed != "mysecretpass"


@pytest.mark.asyncio
async def test_hash_password_produces_different_hashes() -> None:
    hash1 = AuthService.hash_password("samepassword")
    hash2 = AuthService.hash_password("samepassword")
    assert hash1 != hash2  # different salts


@pytest.mark.asyncio
async def test_verify_password_correct() -> None:
    password = "testpass123"
    hashed = AuthService.hash_password(password)
    assert AuthService.verify_password(password, hashed) is True


@pytest.mark.asyncio
async def test_verify_password_incorrect() -> None:
    hashed = AuthService.hash_password("correct_password")
    assert AuthService.verify_password("wrong_password", hashed) is False


# --- authenticate_user ---


@pytest.mark.asyncio
async def test_authenticate_user_success(mock_user: User) -> None:
    mock_user.hashed_password = AuthService.hash_password("testpass123")
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

    service = AuthService(user_repository=mock_user_repo)
    result = await service.authenticate_user("test@example.com", "testpass123")

    assert result == mock_user
    mock_user_repo.get_by_email.assert_called_once_with("test@example.com")


@pytest.mark.asyncio
async def test_authenticate_user_not_found() -> None:
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=None)

    service = AuthService(user_repository=mock_user_repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("missing@example.com", "testpass123")

    assert exc_info.value.status_code == 401
    assert "Invalid email or password" in exc_info.value.detail


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(mock_user: User) -> None:
    mock_user.hashed_password = AuthService.hash_password("correct_password")
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

    service = AuthService(user_repository=mock_user_repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("test@example.com", "wrong_password")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_user_no_hashed_password(mock_user: User) -> None:
    mock_user.hashed_password = None
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

    service = AuthService(user_repository=mock_user_repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("test@example.com", "testpass123")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_authenticate_user_rejects_inactive_account(mock_user: User) -> None:
    """Deactivated users (soft-deleted via admin) cannot log in, even with correct password."""
    mock_user.hashed_password = AuthService.hash_password("testpass123")
    mock_user.is_active = False
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_email = AsyncMock(return_value=mock_user)

    service = AuthService(user_repository=mock_user_repo)
    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user("test@example.com", "testpass123")

    assert exc_info.value.status_code == 403
    assert "deactivated" in exc_info.value.detail.lower()


# --- create_tokens ---


@pytest.mark.asyncio
async def test_create_tokens_returns_token_response() -> None:
    result = AuthService.create_tokens(user_id=42)

    assert isinstance(result, TokenResponse)
    assert result.token_type == "bearer"
    assert isinstance(result.access_token, str)
    assert isinstance(result.refresh_token, str)


@pytest.mark.asyncio
async def test_create_tokens_access_token_valid() -> None:
    result = AuthService.create_tokens(user_id=42)
    payload = decode_token(result.access_token)

    assert payload["sub"] == "42"
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_create_tokens_refresh_token_valid() -> None:
    result = AuthService.create_tokens(user_id=42)
    payload = decode_token(result.refresh_token)

    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"


# --- refresh_access_token ---


@pytest.mark.asyncio
async def test_refresh_access_token_success() -> None:
    tokens = AuthService.create_tokens(user_id=7)
    result = AuthService.refresh_access_token(tokens.refresh_token)

    assert isinstance(result, TokenResponse)
    payload = decode_token(result.access_token)
    assert payload["sub"] == "7"
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_refresh_access_token_with_access_token_fails() -> None:
    tokens = AuthService.create_tokens(user_id=7)

    with pytest.raises(HTTPException) as exc_info:
        AuthService.refresh_access_token(tokens.access_token)

    assert exc_info.value.status_code == 401
    assert "Invalid token type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_access_token_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        AuthService.refresh_access_token("invalid.token.string")

    assert exc_info.value.status_code == 401
    assert "Invalid refresh token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_refresh_access_token_expired() -> None:
    from datetime import UTC, datetime, timedelta

    expired_payload = {
        "sub": "1",
        "exp": datetime.now(UTC) - timedelta(days=1),
        "type": "refresh",
    }
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        AuthService.refresh_access_token(expired_token)

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()
