from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.modules.auth.jwt_handler import JWTBearer


def _make_request_with_auth_header(header_value: str) -> MagicMock:
    request = MagicMock()
    request.headers = {"Authorization": header_value}
    return request


@pytest.mark.asyncio
async def test_jwt_bearer_accepts_valid_bearer_token() -> None:
    bearer = JWTBearer()
    valid_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="good-token")

    with patch(
        "fastapi.security.HTTPBearer.__call__",
        new=AsyncMock(return_value=valid_credentials),
    ), patch(
        "app.modules.auth.jwt_handler.decode_token",
        return_value={"sub": "1", "type": "access"},
    ):
        result = await bearer(_make_request_with_auth_header("Bearer good-token"))

    assert result == "good-token"


@pytest.mark.asyncio
async def test_jwt_bearer_rejects_non_bearer_scheme() -> None:
    bearer = JWTBearer()
    non_bearer_credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="abc")

    with patch(
        "fastapi.security.HTTPBearer.__call__",
        new=AsyncMock(return_value=non_bearer_credentials),
    ), pytest.raises(HTTPException) as exc_info:
        await bearer(_make_request_with_auth_header("Basic abc"))

    assert exc_info.value.status_code == 403
    assert "scheme" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_jwt_bearer_rejects_invalid_token() -> None:
    bearer = JWTBearer()
    valid_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")

    with patch(
        "fastapi.security.HTTPBearer.__call__",
        new=AsyncMock(return_value=valid_credentials),
    ), patch(
        "app.modules.auth.jwt_handler.decode_token",
        side_effect=Exception("bad signature"),
    ), pytest.raises(HTTPException) as exc_info:
        await bearer(_make_request_with_auth_header("Bearer bad-token"))

    assert exc_info.value.status_code == 403
    assert "invalid token" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_jwt_bearer_rejects_missing_credentials() -> None:
    bearer = JWTBearer()

    with patch(
        "fastapi.security.HTTPBearer.__call__",
        new=AsyncMock(return_value=None),
    ), pytest.raises(HTTPException) as exc_info:
        await bearer(_make_request_with_auth_header(""))

    assert exc_info.value.status_code == 403
    assert "authorization" in exc_info.value.detail.lower()


def test_verify_jwt_returns_true_for_valid_payload() -> None:
    bearer = JWTBearer()
    with patch(
        "app.modules.auth.jwt_handler.decode_token",
        return_value={"sub": "1", "type": "access"},
    ):
        assert bearer.verify_jwt("some-token") is True


def test_verify_jwt_returns_false_when_decode_raises() -> None:
    bearer = JWTBearer()
    with patch(
        "app.modules.auth.jwt_handler.decode_token",
        side_effect=Exception("invalid"),
    ):
        assert bearer.verify_jwt("bad-token") is False


def test_verify_jwt_returns_false_when_payload_is_none() -> None:
    bearer = JWTBearer()
    with patch(
        "app.modules.auth.jwt_handler.decode_token",
        return_value=None,
    ):
        assert bearer.verify_jwt("empty-token") is False
