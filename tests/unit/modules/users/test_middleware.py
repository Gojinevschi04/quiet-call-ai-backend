from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.modules.users.middleware import get_current_admin_user, get_current_user
from app.modules.users.models import User
from app.modules.users.schema import UserRole


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_user_valid_access_token_returns_user() -> None:
    user = User(id=5, email="ana@example.com", role=UserRole.USER, hashed_password="x")
    user_repository = MagicMock()
    user_repository.get_by_id = AsyncMock(return_value=user)

    with patch(
        "app.modules.users.middleware.decode_token",
        return_value={"sub": "5", "type": "access"},
    ):
        result = await get_current_user(
            credentials=_make_credentials("valid-token"),
            user_repository=user_repository,
        )

    assert result is user
    user_repository.get_by_id.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_get_current_user_expired_token_raises_401() -> None:
    user_repository = MagicMock()

    with patch(
        "app.modules.users.middleware.decode_token",
        side_effect=jwt.ExpiredSignatureError(),
    ), pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=_make_credentials("expired"),
            user_repository=user_repository,
        )

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401() -> None:
    user_repository = MagicMock()

    with patch(
        "app.modules.users.middleware.decode_token",
        side_effect=jwt.InvalidTokenError(),
    ), pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=_make_credentials("invalid"),
            user_repository=user_repository,
        )

    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_refresh_token_rejected() -> None:
    user_repository = MagicMock()

    with patch(
        "app.modules.users.middleware.decode_token",
        return_value={"sub": "5", "type": "refresh"},
    ), pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=_make_credentials("refresh-token"),
            user_repository=user_repository,
        )

    assert exc_info.value.status_code == 401
    assert "token type" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_reset_token_rejected() -> None:
    user_repository = MagicMock()

    with patch(
        "app.modules.users.middleware.decode_token",
        return_value={"sub": "5", "type": "reset"},
    ), pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=_make_credentials("reset-token"),
            user_repository=user_repository,
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_user_not_in_db_raises_401() -> None:
    user_repository = MagicMock()
    user_repository.get_by_id = AsyncMock(return_value=None)

    with patch(
        "app.modules.users.middleware.decode_token",
        return_value={"sub": "999", "type": "access"},
    ), pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            credentials=_make_credentials("orphan-token"),
            user_repository=user_repository,
        )

    assert exc_info.value.status_code == 401
    assert "user not found" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_admin_user_admin_passes_through() -> None:
    admin_user = User(id=1, email="admin@example.com", role=UserRole.ADMIN, hashed_password="x")

    result = await get_current_admin_user(current_user=admin_user)

    assert result is admin_user


@pytest.mark.asyncio
async def test_get_current_admin_user_regular_user_raises_403() -> None:
    regular_user = User(id=2, email="user@example.com", role=UserRole.USER, hashed_password="x")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin_user(current_user=regular_user)

    assert exc_info.value.status_code == 403
    assert "permissions" in exc_info.value.detail.lower()
