from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_initiate_call() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_call = MagicMock()
        mock_call.sid = "CA123456"
        mock_client.calls.create.return_value = mock_call

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        # Patch _run_sync to just call the function directly
        adapter._run_sync = AsyncMock(return_value=mock_call)

        result = await adapter.initiate_call("+37312345678", "https://example.com/webhook")

        assert result == "CA123456"


@pytest.mark.asyncio
async def test_hangup() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        adapter._run_sync = AsyncMock(return_value=None)

        await adapter.hangup("CA123456")
        adapter._run_sync.assert_called_once()


@pytest.mark.asyncio
async def test_get_call_status() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_call = MagicMock()
        mock_call.status = "completed"

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        adapter._run_sync = AsyncMock(return_value=mock_call)

        result = await adapter.get_call_status("CA123456")
        assert result == "completed"


@pytest.mark.asyncio
async def test_get_recording_url() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_recording = MagicMock()
        mock_recording.uri = "/2010-04-01/Accounts/AC123/Recordings/RE123.json"

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        adapter._run_sync = AsyncMock(return_value=[mock_recording])

        result = await adapter.get_recording_url("CA123456")
        assert result == "https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE123.mp3"


@pytest.mark.asyncio
async def test_get_recording_url_none() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        adapter._run_sync = AsyncMock(return_value=[])

        result = await adapter.get_recording_url("CA123456")
        assert result is None


@pytest.mark.asyncio
async def test_initiate_call_retry_on_failure() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings, \
         patch("app.integrations.twilio_adapter.asyncio") as mock_asyncio:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"
        mock_asyncio.sleep = AsyncMock()
        mock_asyncio.get_event_loop = MagicMock()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_call = MagicMock()
        mock_call.sid = "CA_RETRY"

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        # First two attempts fail, third succeeds
        adapter._run_sync = AsyncMock(
            side_effect=[Exception("busy"), Exception("no-answer"), mock_call]
        )

        result = await adapter.initiate_call("+37312345678", "https://example.com/webhook")

        assert result == "CA_RETRY"
        assert adapter._run_sync.call_count == 3
        assert mock_asyncio.sleep.call_count == 2  # slept between retries


@pytest.mark.asyncio
async def test_initiate_call_all_retries_fail() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings, \
         patch("app.integrations.twilio_adapter.asyncio") as mock_asyncio:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"
        mock_asyncio.sleep = AsyncMock()
        mock_asyncio.get_event_loop = MagicMock()

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        adapter._run_sync = AsyncMock(side_effect=Exception("Connection refused"))

        with pytest.raises(Exception, match="Connection refused"):
            await adapter.initiate_call("+37312345678", "https://example.com/webhook")

        assert adapter._run_sync.call_count == 3  # MAX_CALL_RETRIES


@pytest.mark.asyncio
async def test_get_recording_audio() -> None:
    with patch("app.integrations.twilio_adapter.Client") as mock_client_cls, \
         patch("app.integrations.twilio_adapter.settings") as mock_settings, \
         patch("app.integrations.twilio_adapter.httpx") as mock_httpx:
        mock_settings.TWILIO_ACCOUNT_SID = "test-sid"
        mock_settings.TWILIO_AUTH_TOKEN = "test-token"
        mock_settings.TWILIO_PHONE_NUMBER = "+15551234567"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = b"wav_audio_data"
        mock_response.raise_for_status = MagicMock()

        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client.get = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value = mock_async_client

        from app.integrations.twilio_adapter import TwilioAdapter

        adapter = TwilioAdapter()
        result = await adapter.get_recording_audio("https://api.twilio.com/rec/123.wav")

        assert result == b"wav_audio_data"
