from unittest.mock import patch

import jwt
import pytest

from app.modules.calls.ws import _authenticate_ws


@pytest.mark.asyncio
async def test_authenticate_ws_valid_token() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": "42", "type": "access"}
        user_id, is_admin = await _authenticate_ws("valid_token")
        assert user_id == 42
        assert is_admin is False


@pytest.mark.asyncio
async def test_authenticate_ws_admin_token() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": "1", "type": "access", "role": "admin"}
        user_id, is_admin = await _authenticate_ws("admin_token")
        assert user_id == 1
        assert is_admin is True


@pytest.mark.asyncio
async def test_authenticate_ws_no_token() -> None:
    user_id, is_admin = await _authenticate_ws(None)
    assert user_id is None
    assert is_admin is False


@pytest.mark.asyncio
async def test_authenticate_ws_expired_token() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.side_effect = jwt.ExpiredSignatureError()
        user_id, is_admin = await _authenticate_ws("expired_token")
        assert user_id is None
        assert is_admin is False


@pytest.mark.asyncio
async def test_authenticate_ws_invalid_token() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.side_effect = jwt.InvalidTokenError()
        user_id, is_admin = await _authenticate_ws("bad_token")
        assert user_id is None
        assert is_admin is False


@pytest.mark.asyncio
async def test_authenticate_ws_wrong_token_type() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": "42", "type": "refresh"}
        user_id, is_admin = await _authenticate_ws("refresh_token")
        assert user_id is None
        assert is_admin is False
