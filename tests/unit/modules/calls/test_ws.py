from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import WebSocketDisconnect

from app.modules.calls.ws import WS_CLOSE_UNAUTHORIZED, _authenticate_ws, call_status_ws


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


@pytest.mark.asyncio
async def test_authenticate_ws_non_numeric_sub_rejected() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.return_value = {"sub": "not-an-int", "type": "access"}
        user_id, is_admin = await _authenticate_ws("bad-sub")
        assert user_id is None
        assert is_admin is False


@pytest.mark.asyncio
async def test_authenticate_ws_missing_sub_rejected() -> None:
    with patch("app.modules.calls.ws.decode_token") as mock_decode:
        mock_decode.return_value = {"type": "access"}
        user_id, is_admin = await _authenticate_ws("no-sub")
        assert user_id is None
        assert is_admin is False


@pytest.mark.asyncio
async def test_call_status_ws_unauthorized_closes_with_4001() -> None:
    websocket = MagicMock()
    websocket.close = AsyncMock()

    with patch(
        "app.modules.calls.ws._authenticate_ws",
        new=AsyncMock(return_value=(None, False)),
    ), patch("app.modules.calls.ws.call_broadcaster") as mock_broadcaster:
        await call_status_ws(websocket=websocket, task_id=1, token="bad-token")

    websocket.close.assert_awaited_once()
    close_kwargs = websocket.close.await_args.kwargs
    assert close_kwargs["code"] == WS_CLOSE_UNAUTHORIZED
    mock_broadcaster.connect.assert_not_called()


@pytest.mark.asyncio
async def test_call_status_ws_authorized_connects_and_cleans_up_on_disconnect() -> None:
    websocket = MagicMock()
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    websocket.close = AsyncMock()

    with patch(
        "app.modules.calls.ws._authenticate_ws",
        new=AsyncMock(return_value=(42, False)),
    ), patch("app.modules.calls.ws.call_broadcaster") as mock_broadcaster:
        mock_broadcaster.connect = AsyncMock()
        mock_broadcaster.disconnect = AsyncMock()

        await call_status_ws(websocket=websocket, task_id=5, token="ok")

    mock_broadcaster.connect.assert_awaited_once_with(5, websocket)
    mock_broadcaster.disconnect.assert_awaited_once_with(5, websocket)


@pytest.mark.asyncio
async def test_call_status_ws_cleans_up_even_on_unexpected_error() -> None:
    websocket = MagicMock()
    websocket.receive_text = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "app.modules.calls.ws._authenticate_ws",
        new=AsyncMock(return_value=(7, True)),
    ), patch("app.modules.calls.ws.call_broadcaster") as mock_broadcaster:
        mock_broadcaster.connect = AsyncMock()
        mock_broadcaster.disconnect = AsyncMock()

        with pytest.raises(RuntimeError):
            await call_status_ws(websocket=websocket, task_id=9, token="admin")

    mock_broadcaster.disconnect.assert_awaited_once_with(9, websocket)
