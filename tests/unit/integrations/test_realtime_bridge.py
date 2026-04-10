import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.realtime_bridge import (
    LANG_DISPLAY_NAMES,
    MAX_SILENCE_NUDGES,
    NUDGE_PHRASES,
    REPORT_OUTCOME_TOOL,
    RETRY_LATER_PHRASES,
    RealtimeBridge,
)
from app.modules.calls.schema import Speaker


def _make_bridge(language: str = "en") -> RealtimeBridge:
    mock_twilio_ws = MagicMock()
    mock_twilio_ws.send_json = AsyncMock()
    mock_twilio_ws.client_state = None
    return RealtimeBridge(
        twilio_ws=mock_twilio_ws,
        task_id=42,
        user_id=7,
        language=language,
        system_prompt="You are Ana.",
    )


def test_report_outcome_tool_schema_is_valid() -> None:
    assert REPORT_OUTCOME_TOOL["type"] == "function"
    assert REPORT_OUTCOME_TOOL["name"] == "report_outcome"
    params = REPORT_OUTCOME_TOOL["parameters"]
    assert set(params["required"]) == {"status", "reason"}
    assert set(params["properties"]["status"]["enum"]) == {"achieved", "failed", "rejected"}


def test_lang_display_names_covers_all_supported_languages() -> None:
    assert LANG_DISPLAY_NAMES == {"en": "English", "ru": "Russian", "ro": "Romanian"}


def test_nudge_phrases_and_retry_later_cover_all_languages() -> None:
    for language_code in ("en", "ru", "ro"):
        assert language_code in NUDGE_PHRASES
        assert language_code in RETRY_LATER_PHRASES
        assert NUDGE_PHRASES[language_code]
        assert RETRY_LATER_PHRASES[language_code]


def test_record_transcript_appends_entry_to_buffer() -> None:
    bridge = _make_bridge()
    bridge._record_transcript(Speaker.AGENT, "Hello")
    bridge._record_transcript(Speaker.INTERLOCUTOR, "Hi")

    assert len(bridge.transcript_buffer) == 2
    assert bridge.transcript_buffer[0]["speaker"] == Speaker.AGENT
    assert bridge.transcript_buffer[0]["text"] == "Hello"
    assert bridge.transcript_buffer[1]["speaker"] == Speaker.INTERLOCUTOR


def test_cancel_idle_timer_is_safe_when_no_timer() -> None:
    bridge = _make_bridge()
    bridge._cancel_idle_timer()
    assert bridge._idle_timer is None


@pytest.mark.asyncio
async def test_handle_function_call_sets_outcome_and_queues_hangup() -> None:
    bridge = _make_bridge("ro")
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    await bridge._handle_function_call({
        "name": "report_outcome",
        "call_id": "call-abc",
        "arguments": json.dumps({"status": "achieved", "reason": "Info obținută."}),
    })

    assert bridge.outcome == {"status": "achieved", "reason": "Info obținută."}
    assert bridge._hangup_pending is True
    assert bridge.openai_ws.send.await_count == 2
    first_sent = json.loads(bridge.openai_ws.send.call_args_list[0].args[0])
    second_sent = json.loads(bridge.openai_ws.send.call_args_list[1].args[0])
    assert first_sent["type"] == "conversation.item.create"
    assert first_sent["item"]["call_id"] == "call-abc"
    assert second_sent["type"] == "response.create"


@pytest.mark.asyncio
async def test_handle_function_call_ignores_unknown_tool() -> None:
    bridge = _make_bridge()
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    await bridge._handle_function_call({
        "name": "not_a_real_tool",
        "call_id": "call-xyz",
        "arguments": "{}",
    })

    assert bridge.outcome is None
    bridge.openai_ws.send.assert_not_called()


@pytest.mark.asyncio
async def test_handle_function_call_handles_invalid_json_arguments() -> None:
    bridge = _make_bridge()
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    await bridge._handle_function_call({
        "name": "report_outcome",
        "call_id": "call-1",
        "arguments": "this is not json",
    })

    assert bridge.outcome == {"status": "failed", "reason": ""}


@pytest.mark.asyncio
async def test_handle_barge_in_skips_when_no_assistant_item() -> None:
    bridge = _make_bridge()
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    await bridge._handle_barge_in()

    bridge.openai_ws.send.assert_not_called()


@pytest.mark.asyncio
async def test_handle_idle_timeout_triggers_failed_outcome_after_max_nudges() -> None:
    bridge = _make_bridge("ro")
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    import websockets.protocol
    bridge.openai_ws.state = websockets.protocol.State.OPEN

    bridge._silence_nudges = MAX_SILENCE_NUDGES - 1
    await bridge._handle_idle_timeout(timeout_seconds=0.0)

    assert bridge._silence_nudges == MAX_SILENCE_NUDGES
    assert bridge.outcome is not None
    assert bridge.outcome["status"] == "failed"
    assert "No response" in bridge.outcome["reason"]
    assert bridge._hangup_pending is True


@pytest.mark.asyncio
async def test_handle_idle_timeout_sends_nudge_when_below_max() -> None:
    bridge = _make_bridge("en")
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    import websockets.protocol
    bridge.openai_ws.state = websockets.protocol.State.OPEN

    await bridge._handle_idle_timeout(timeout_seconds=0.0)

    assert bridge._silence_nudges == 1
    assert bridge.outcome is None
    assert bridge._hangup_pending is False
    sent_payload = json.loads(bridge.openai_ws.send.call_args.args[0])
    assert sent_payload["type"] == "response.create"
    assert NUDGE_PHRASES["en"] in sent_payload["response"]["instructions"]


@pytest.mark.asyncio
async def test_handle_idle_timeout_noops_when_ws_closed() -> None:
    bridge = _make_bridge()
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()

    import websockets.protocol
    bridge.openai_ws.state = websockets.protocol.State.CLOSED

    await bridge._handle_idle_timeout(timeout_seconds=0.0)

    bridge.openai_ws.send.assert_not_called()
    assert bridge._silence_nudges == 0


@pytest.mark.asyncio
async def test_handle_duration_timeout_sets_failed_outcome_and_queues_hangup() -> None:
    from unittest.mock import patch as mock_patch

    import websockets.protocol

    bridge = _make_bridge("ro")
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()
    bridge.openai_ws.state = websockets.protocol.State.OPEN

    with mock_patch("app.core.config.settings.MAX_CALL_DURATION_SECONDS", 0):
        await bridge._handle_duration_timeout()

    assert bridge.outcome is not None
    assert bridge.outcome["status"] == "failed"
    assert "Max call duration" in bridge.outcome["reason"]
    assert bridge._hangup_pending is True
    bridge.openai_ws.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_duration_timeout_respects_existing_outcome() -> None:
    from unittest.mock import patch as mock_patch

    import websockets.protocol

    bridge = _make_bridge()
    bridge.outcome = {"status": "achieved", "reason": "Already done."}
    bridge.openai_ws = MagicMock()
    bridge.openai_ws.send = AsyncMock()
    bridge.openai_ws.state = websockets.protocol.State.OPEN

    with mock_patch("app.core.config.settings.MAX_CALL_DURATION_SECONDS", 0):
        await bridge._handle_duration_timeout()

    assert bridge.outcome["status"] == "achieved"
    bridge.openai_ws.send.assert_not_called()


def test_cancel_duration_timer_is_safe_when_no_timer() -> None:
    bridge = _make_bridge()
    bridge._cancel_duration_timer()
    assert bridge._duration_timer is None


def test_init_failed_defaults_to_false() -> None:
    bridge = _make_bridge()
    assert bridge.init_failed is False


@pytest.mark.asyncio
async def test_run_sets_init_failed_true_when_openai_connect_raises() -> None:
    from unittest.mock import patch as mock_patch

    bridge = _make_bridge()

    async def _fake_connect(*args, **kwargs) -> None:  # noqa: ARG001
        raise ConnectionRefusedError("cannot reach OpenAI")

    with mock_patch("app.integrations.realtime_bridge.websockets.connect", side_effect=_fake_connect):
        await bridge.run()

    assert bridge.init_failed is True
