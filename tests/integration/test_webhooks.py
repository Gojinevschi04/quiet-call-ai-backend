from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_twilio_call_callback(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/calls/1",
        data={"CallSid": "CA123", "CallStatus": "answered"},
    )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Response>" in response.text
    assert "<Pause" in response.text


@pytest.mark.asyncio
async def test_twilio_status_callback_completed(client: AsyncClient) -> None:
    with patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get:
        mock_session = MagicMock()
        mock_session.duration = None
        mock_get.return_value = mock_session

        with patch("app.modules.calls.repository.CallSessionRepository.update") as mock_update:
            mock_update.return_value = mock_session

            response = await client.post(
                "/webhooks/calls/1/status",
                data={"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "45"},
            )
            assert response.status_code == 200
            assert mock_session.duration == 45


@pytest.mark.asyncio
async def test_twilio_status_callback_failed(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock

    from app.modules.tasks.schema import TaskStatus

    mock_task = MagicMock()
    mock_task.status = TaskStatus.IN_PROGRESS

    with (
        patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get,
        patch("app.modules.calls.repository.CallSessionRepository.update") as mock_update,
        patch(
            "app.modules.tasks.repository.TaskRepository.get_by_id_any_user",
            new=AsyncMock(return_value=mock_task),
        ),
        patch("app.modules.tasks.repository.TaskRepository.update", new=AsyncMock(return_value=mock_task)),
    ):
        mock_session = MagicMock()
        mock_get.return_value = mock_session
        mock_update.return_value = mock_session

        response = await client.post(
            "/webhooks/calls/1/status",
            data={"CallSid": "CA123", "CallStatus": "failed", "CallDuration": "0"},
        )
        assert response.status_code == 200
        assert mock_session.duration == 0
        assert mock_task.status == TaskStatus.FAILED
        assert "failed" in mock_task.error_reason


@pytest.mark.asyncio
async def test_twilio_recording_callback(client: AsyncClient) -> None:
    with patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get:
        mock_session = MagicMock()
        mock_get.return_value = mock_session

        with patch("app.modules.calls.repository.CallSessionRepository.update") as mock_update:
            mock_update.return_value = mock_session

            response = await client.post(
                "/webhooks/calls/1/recording",
                data={"RecordingUrl": "https://api.twilio.com/rec/123.wav", "RecordingDuration": "30"},
            )
            assert response.status_code == 200
            assert mock_session.recording_uri == "https://api.twilio.com/rec/123.wav"


@pytest.mark.asyncio
async def test_twilio_status_callback_no_session(client: AsyncClient) -> None:
    with patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get:
        mock_get.return_value = None
        response = await client.post(
            "/webhooks/calls/999/status",
            data={"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "10"},
        )
        assert response.status_code == 200  # gracefully handles missing session


@pytest.mark.asyncio
async def test_twilio_status_callback_malformed_duration(client: AsyncClient) -> None:
    with patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get:
        mock_session = MagicMock()
        mock_session.duration = None
        mock_get.return_value = mock_session

        with patch("app.modules.calls.repository.CallSessionRepository.update") as mock_update:
            mock_update.return_value = mock_session

            response = await client.post(
                "/webhooks/calls/1/status",
                data={"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "not-a-number"},
            )
            assert response.status_code == 200
            assert mock_session.duration == 0  # gracefully defaults to 0


@pytest.mark.asyncio
async def test_twilio_recording_callback_no_session(client: AsyncClient) -> None:
    with patch("app.modules.calls.repository.CallSessionRepository.get_by_task_id") as mock_get:
        mock_get.return_value = None
        response = await client.post(
            "/webhooks/calls/999/recording",
            data={"RecordingUrl": "https://example.com/rec.wav", "RecordingDuration": "30"},
        )
        assert response.status_code == 200  # gracefully handles missing session


@pytest.mark.asyncio
async def test_twilio_gather_callback(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/calls/1/gather",
        data={"SpeechResult": "Yes, March 20 please.", "Confidence": "0.95", "CallSid": "CA123"},
    )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Pause" in response.text


@pytest.mark.asyncio
async def test_twilio_gather_callback_empty_speech(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/calls/1/gather",
        data={"SpeechResult": "", "Confidence": "0", "CallSid": "CA123"},
    )
    assert response.status_code == 200


# --- Regression: Twilio decline CallStatus flips IN_PROGRESS task to FAILED and emits WS event ---


@pytest.mark.parametrize("call_status", ["busy", "no-answer", "canceled"])
@pytest.mark.asyncio
async def test_twilio_status_callback_decline_flips_task_to_failed_and_emits(
    client: AsyncClient,
    call_status: str,
) -> None:
    from unittest.mock import AsyncMock

    from app.modules.tasks.schema import TaskStatus

    mock_task = MagicMock()
    mock_task.status = TaskStatus.IN_PROGRESS
    mock_task.error_reason = None

    mock_call_session = MagicMock()
    mock_call_session.duration = None

    mock_broadcaster = MagicMock()
    mock_broadcaster.has_listeners = MagicMock(return_value=True)
    mock_broadcaster.emit = AsyncMock()

    with (
        patch(
            "app.modules.calls.repository.CallSessionRepository.get_by_task_id",
            new=AsyncMock(return_value=mock_call_session),
        ),
        patch(
            "app.modules.calls.repository.CallSessionRepository.update",
            new=AsyncMock(return_value=mock_call_session),
        ),
        patch(
            "app.modules.tasks.repository.TaskRepository.get_by_id_any_user",
            new=AsyncMock(return_value=mock_task),
        ),
        patch(
            "app.modules.tasks.repository.TaskRepository.update",
            new=AsyncMock(return_value=mock_task),
        ),
        patch("app.modules.webhooks.views.call_broadcaster", mock_broadcaster),
    ):
        response = await client.post(
            "/webhooks/calls/1/status",
            data={"CallSid": "CA123", "CallStatus": call_status, "CallDuration": "0"},
        )

    assert response.status_code == 200
    assert mock_task.status == TaskStatus.FAILED
    assert mock_task.error_reason is not None and len(mock_task.error_reason) > 0
    assert call_status in mock_task.error_reason
    mock_broadcaster.emit.assert_awaited_once()
    emit_args = mock_broadcaster.emit.await_args
    assert emit_args.args[0] == 1
    assert emit_args.args[1] == "call_ended"


# --- Regression: voicemail detection flips IN_PROGRESS task to FAILED and emits WS ---


@pytest.mark.asyncio
async def test_twilio_status_callback_voicemail_flips_task_to_failed(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock

    from app.modules.tasks.schema import TaskStatus

    mock_task = MagicMock()
    mock_task.status = TaskStatus.IN_PROGRESS
    mock_task.error_reason = None

    mock_broadcaster = MagicMock()
    mock_broadcaster.has_listeners = MagicMock(return_value=True)
    mock_broadcaster.emit = AsyncMock()

    with (
        patch(
            "app.modules.tasks.repository.TaskRepository.get_by_id_any_user",
            new=AsyncMock(return_value=mock_task),
        ),
        patch(
            "app.modules.tasks.repository.TaskRepository.update",
            new=AsyncMock(return_value=mock_task),
        ),
        patch(
            "app.modules.calls.repository.CallSessionRepository.get_by_task_id",
            new=AsyncMock(return_value=None),
        ),
        patch("app.modules.webhooks.views.call_broadcaster", mock_broadcaster),
        patch(
            "app.integrations.twilio_adapter.TwilioAdapter.hangup",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await client.post(
            "/webhooks/calls/1/status",
            data={
                "CallSid": "CA123",
                "CallStatus": "in-progress",
                "AnsweredBy": "machine_end_beep",
                "CallDuration": "0",
            },
        )

    assert response.status_code == 200
    assert mock_task.status == TaskStatus.FAILED
    assert "voicemail" in mock_task.error_reason.lower()
    mock_broadcaster.emit.assert_awaited_once()
    emit_args = mock_broadcaster.emit.await_args
    assert emit_args.args[1] == "call_ended"


@pytest.mark.asyncio
async def test_twilio_status_callback_voicemail_ignored_on_terminal_task(client: AsyncClient) -> None:
    """Task already COMPLETED must not be flipped back to FAILED, and no WS emit."""
    from unittest.mock import AsyncMock

    from app.modules.tasks.schema import TaskStatus

    mock_task = MagicMock()
    mock_task.status = TaskStatus.COMPLETED
    mock_task.error_reason = None

    mock_broadcaster = MagicMock()
    mock_broadcaster.has_listeners = MagicMock(return_value=True)
    mock_broadcaster.emit = AsyncMock()

    task_update_mock = AsyncMock(return_value=mock_task)

    with (
        patch(
            "app.modules.tasks.repository.TaskRepository.get_by_id_any_user",
            new=AsyncMock(return_value=mock_task),
        ),
        patch(
            "app.modules.tasks.repository.TaskRepository.update",
            new=task_update_mock,
        ),
        patch(
            "app.modules.calls.repository.CallSessionRepository.get_by_task_id",
            new=AsyncMock(return_value=None),
        ),
        patch("app.modules.webhooks.views.call_broadcaster", mock_broadcaster),
        patch(
            "app.integrations.twilio_adapter.TwilioAdapter.hangup",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await client.post(
            "/webhooks/calls/1/status",
            data={
                "CallSid": "CA123",
                "CallStatus": "in-progress",
                "AnsweredBy": "machine_end_beep",
                "CallDuration": "0",
            },
        )

    assert response.status_code == 200
    assert mock_task.status == TaskStatus.COMPLETED
    task_update_mock.assert_not_called()
    mock_broadcaster.emit.assert_not_called()


# --- Twilio signature validation ---


@pytest.mark.asyncio
async def test_twilio_status_callback_rejects_missing_signature() -> None:
    """Regression: webhook without X-Twilio-Signature header is 403 when auth token is set."""
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.modules.webhooks.views import verify_twilio_signature

    if verify_twilio_signature in app.dependency_overrides:
        del app.dependency_overrides[verify_twilio_signature]
    try:
        with patch("app.modules.webhooks.views.settings.TWILIO_AUTH_TOKEN", "fake-token"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.post(
                    "/webhooks/calls/1/status",
                    data={"CallSid": "CA123", "CallStatus": "completed"},
                )
                assert response.status_code == 403
    finally:

        async def _noop() -> None:
            return None

        app.dependency_overrides[verify_twilio_signature] = _noop


@pytest.mark.asyncio
async def test_twilio_status_callback_rejects_forged_signature() -> None:
    """Regression: wrong signature is rejected with 403."""
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.modules.webhooks.views import verify_twilio_signature

    if verify_twilio_signature in app.dependency_overrides:
        del app.dependency_overrides[verify_twilio_signature]
    try:
        with patch("app.modules.webhooks.views.settings.TWILIO_AUTH_TOKEN", "real-token"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.post(
                    "/webhooks/calls/1/status",
                    data={"CallSid": "CA123"},
                    headers={"X-Twilio-Signature": "forged-garbage"},
                )
                assert response.status_code == 403
    finally:

        async def _noop() -> None:
            return None

        app.dependency_overrides[verify_twilio_signature] = _noop


@pytest.mark.asyncio
async def test_twilio_status_callback_accepts_valid_signature() -> None:
    """Regression: a correctly-signed Twilio webhook is accepted."""
    from unittest.mock import AsyncMock, patch

    from httpx import ASGITransport, AsyncClient
    from twilio.request_validator import RequestValidator

    from app.main import app
    from app.modules.webhooks.views import verify_twilio_signature

    auth_token = "real-token-for-signing"
    if verify_twilio_signature in app.dependency_overrides:
        del app.dependency_overrides[verify_twilio_signature]
    try:
        with (
            patch("app.modules.webhooks.views.settings.TWILIO_AUTH_TOKEN", auth_token),
            patch(
                "app.modules.calls.repository.CallSessionRepository.get_by_task_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            url = "http://test/webhooks/calls/1/status"
            params = {"CallSid": "CA123", "CallStatus": "completed", "CallDuration": "10"}
            validator = RequestValidator(auth_token)
            signature = validator.compute_signature(url, params)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.post(
                    "/webhooks/calls/1/status",
                    data=params,
                    headers={"X-Twilio-Signature": signature},
                )
                assert response.status_code == 200
    finally:

        async def _noop() -> None:
            return None

        app.dependency_overrides[verify_twilio_signature] = _noop


@pytest.mark.asyncio
async def test_verify_twilio_signature_bypasses_when_token_empty() -> None:
    """Regression: empty TWILIO_AUTH_TOKEN (dev/test mode) skips signature check."""
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.modules.webhooks.views import verify_twilio_signature

    if verify_twilio_signature in app.dependency_overrides:
        del app.dependency_overrides[verify_twilio_signature]
    try:
        with patch("app.modules.webhooks.views.settings.TWILIO_AUTH_TOKEN", ""):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.post(
                    "/webhooks/calls/1",
                    data={"CallSid": "CA1", "CallStatus": "answered"},
                )
                assert response.status_code == 200
    finally:

        async def _noop() -> None:
            return None

        app.dependency_overrides[verify_twilio_signature] = _noop


@pytest.mark.asyncio
async def test_twilio_status_callback_signature_check_runs_before_db_lookup() -> None:
    """Regression: signature rejection must precede any task_id lookup so an
    unauthenticated attacker can't probe which task_ids exist via response timing
    or differential DB error.
    """
    from unittest.mock import AsyncMock, patch as real_patch
    from app.main import app
    from app.modules.webhooks.views import verify_twilio_signature
    from httpx import ASGITransport, AsyncClient

    if verify_twilio_signature in app.dependency_overrides:
        del app.dependency_overrides[verify_twilio_signature]
    db_lookup = AsyncMock(return_value=None)
    try:
        with real_patch("app.modules.webhooks.views.settings.TWILIO_AUTH_TOKEN", "real-token"), \
             real_patch(
                 "app.modules.calls.repository.CallSessionRepository.get_by_task_id",
                 new=db_lookup,
             ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as raw:
                response = await raw.post(
                    "/webhooks/calls/999999/status",
                    data={"CallSid": "CA123", "CallStatus": "completed"},
                )
                assert response.status_code == 403
                db_lookup.assert_not_called()
    finally:
        async def _noop() -> None: return None
        app.dependency_overrides[verify_twilio_signature] = _noop
