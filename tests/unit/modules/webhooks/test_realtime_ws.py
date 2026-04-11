import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

from app.integrations.realtime_bridge import RealtimeBridge
from app.modules.calls.models import CallSession
from app.modules.calls.schema import Speaker
from app.modules.tasks.models import Task
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.models import DialogTemplate
from app.modules.webhooks.realtime_ws import (
    SUMMARY_FALLBACK_MAX_CHARS,
    VALID_OUTCOME_STATUSES,
    _classify_outcome_from_transcript,
    _finalize_call,
    _format_transcript_as_conversation,
    _generate_llm_summary,
    _wait_for_start,
)


def _transcript_entry(speaker: Speaker, text: str) -> dict:
    return {"speaker": speaker, "text": text, "timestamp": datetime.now()}


def test_valid_outcome_statuses_covers_expected_values() -> None:
    assert set(VALID_OUTCOME_STATUSES) == {"achieved", "failed", "rejected"}


def test_format_transcript_empty() -> None:
    assert _format_transcript_as_conversation([]) == ""


def test_format_transcript_labels_speakers() -> None:
    transcript = [
        _transcript_entry(Speaker.AGENT, "Hello."),
        _transcript_entry(Speaker.INTERLOCUTOR, "Hi."),
        _transcript_entry(Speaker.AGENT, "Goodbye."),
    ]
    output = _format_transcript_as_conversation(transcript)
    assert output == "Agent: Hello.\nInterlocutor: Hi.\nAgent: Goodbye."


@pytest.mark.asyncio
async def test_generate_llm_summary_empty_transcript_returns_empty() -> None:
    assert await _generate_llm_summary([], "en") == ""


@pytest.mark.asyncio
async def test_generate_llm_summary_returns_llm_response() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Hello.")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(return_value="Scurtă descriere.")
        result = await _generate_llm_summary(transcript, "ro")

    assert result == "Scurtă descriere."


@pytest.mark.asyncio
async def test_generate_llm_summary_falls_back_to_truncated_transcript_on_error() -> None:
    long_agent_text = "A" * (SUMMARY_FALLBACK_MAX_CHARS + 200)
    transcript = [_transcript_entry(Speaker.AGENT, long_agent_text)]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(side_effect=RuntimeError("OpenAI down"))
        result = await _generate_llm_summary(transcript, "en")

    assert len(result) == SUMMARY_FALLBACK_MAX_CHARS


@pytest.mark.asyncio
async def test_classify_outcome_returns_valid_result() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Info?")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(
            return_value='{"status": "achieved", "reason": "Info obtained."}'
        )
        result = await _classify_outcome_from_transcript(transcript, "en", "Get info.")

    assert result == {"status": "achieved", "reason": "Info obtained."}


@pytest.mark.asyncio
async def test_classify_outcome_strips_markdown_code_fences() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Info?")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(
            return_value='```json\n{"status": "failed", "reason": "No answer."}\n```'
        )
        result = await _classify_outcome_from_transcript(transcript, "en", "Get info.")

    assert result is not None
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_classify_outcome_rejects_invalid_status() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Info?")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(
            return_value='{"status": "weird_status", "reason": "..."}'
        )
        result = await _classify_outcome_from_transcript(transcript, "en", "Get info.")

    assert result is None


@pytest.mark.asyncio
async def test_classify_outcome_returns_none_on_llm_error() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Info?")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(side_effect=RuntimeError("API error"))
        result = await _classify_outcome_from_transcript(transcript, "en", "Get info.")

    assert result is None


@pytest.mark.asyncio
async def test_classify_outcome_returns_none_on_invalid_json() -> None:
    transcript = [_transcript_entry(Speaker.AGENT, "Info?")]

    with patch("app.modules.webhooks.realtime_ws.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = mock_adapter_cls.return_value
        mock_adapter.generate_response = AsyncMock(return_value="this is not json at all")
        result = await _classify_outcome_from_transcript(transcript, "en", "Get info.")

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_start_extracts_custom_parameters() -> None:
    start_message = {
        "event": "start",
        "start": {
            "streamSid": "MZ123",
            "callSid": "CA456",
            "customParameters": {
                "task_id": "42",
                "user_id": "7",
                "language": "ro",
                "system_prompt": "You are Ana.",
            },
        },
    }

    mock_websocket = MagicMock()
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps(start_message))

    result = await _wait_for_start(mock_websocket)

    assert result is not None
    assert result["task_id"] == 42
    assert result["user_id"] == 7
    assert result["language"] == "ro"
    assert result["system_prompt"] == "You are Ana."


@pytest.mark.asyncio
async def test_wait_for_start_skips_connected_event() -> None:
    connected_message = {"event": "connected", "protocol": "Call", "version": "1.0.0"}
    start_message = {
        "event": "start",
        "start": {
            "streamSid": "MZ1",
            "callSid": "CA1",
            "customParameters": {"task_id": "1", "user_id": "1"},
        },
    }
    messages_to_return = [json.dumps(connected_message), json.dumps(start_message)]

    mock_websocket = MagicMock()
    mock_websocket.receive_text = AsyncMock(side_effect=messages_to_return)

    result = await _wait_for_start(mock_websocket)

    assert result is not None
    assert result["task_id"] == 1


@pytest.mark.asyncio
async def test_wait_for_start_returns_none_when_ids_missing() -> None:
    start_message = {
        "event": "start",
        "start": {"streamSid": "MZ1", "callSid": "CA1", "customParameters": {}},
    }

    mock_websocket = MagicMock()
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps(start_message))

    result = await _wait_for_start(mock_websocket)

    assert result is None


def _make_bridge_with_transcript(
    language: str = "en",
    outcome: dict | None = None,
) -> RealtimeBridge:
    mock_twilio_ws = MagicMock()
    mock_twilio_ws.client_state = WebSocketState.CONNECTED
    bridge = RealtimeBridge(
        twilio_ws=mock_twilio_ws,
        task_id=42,
        user_id=7,
        language=language,
        system_prompt="p",
    )
    bridge.call_sid = "CA999"
    bridge.stream_start_time = datetime.now()
    bridge.transcript_buffer = [
        {"speaker": Speaker.AGENT, "text": "Hello.", "timestamp": datetime.now()},
        {"speaker": Speaker.INTERLOCUTOR, "text": "Hi.", "timestamp": datetime.now()},
    ]
    bridge.outcome = outcome
    return bridge


def _build_finalize_mocks(task: Task | None, template: DialogTemplate | None,
                          call_session: CallSession | None) -> dict:
    task_repo = MagicMock()
    task_repo.get_by_id_any_user = AsyncMock(return_value=task)
    task_repo.update = AsyncMock()

    template_repo = MagicMock()
    template_repo.get_by_id = AsyncMock(return_value=template)

    call_session_repo = MagicMock()
    call_session_repo.get_by_task_id = AsyncMock(return_value=call_session)
    call_session_repo.update = AsyncMock()

    log_line_repo = MagicMock()
    log_line_repo.create_many = AsyncMock()

    user_repo = MagicMock()

    return {
        "task_repo": task_repo,
        "template_repo": template_repo,
        "call_session_repo": call_session_repo,
        "log_line_repo": log_line_repo,
        "user_repo": user_repo,
    }


def _patch_finalize_dependencies(mocks: dict) -> list:
    """Return a list of context managers to apply around _finalize_call."""
    mock_session = AsyncMock()

    session_ctx = patch("app.modules.webhooks.realtime_ws.async_session")
    task_repo_ctx = patch(
        "app.modules.webhooks.realtime_ws.TaskRepository", return_value=mocks["task_repo"]
    )
    template_repo_ctx = patch(
        "app.modules.webhooks.realtime_ws.TemplateRepository", return_value=mocks["template_repo"]
    )
    call_repo_ctx = patch(
        "app.modules.webhooks.realtime_ws.CallSessionRepository",
        return_value=mocks["call_session_repo"],
    )
    log_repo_ctx = patch(
        "app.modules.webhooks.realtime_ws.LogLineRepository",
        return_value=mocks["log_line_repo"],
    )
    user_repo_ctx = patch(
        "app.modules.webhooks.realtime_ws.UserRepository", return_value=mocks["user_repo"]
    )
    post_call_ctx = patch("app.modules.webhooks.realtime_ws.PostCallProcessor")
    twilio_ctx = patch("app.modules.webhooks.realtime_ws.TwilioAdapter")

    session_mock = session_ctx.start()
    session_mock.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    session_mock.return_value.__aexit__ = AsyncMock(return_value=False)

    task_repo_ctx.start()
    template_repo_ctx.start()
    call_repo_ctx.start()
    log_repo_ctx.start()
    user_repo_ctx.start()
    post_call_mock = post_call_ctx.start()
    post_call_mock.return_value.process = AsyncMock()
    twilio_mock = twilio_ctx.start()
    twilio_mock.return_value.get_recording_url = AsyncMock(return_value=None)

    return [
        session_ctx, task_repo_ctx, template_repo_ctx, call_repo_ctx,
        log_repo_ctx, user_repo_ctx, post_call_ctx, twilio_ctx,
    ]


def _stop_patches(contexts: list) -> None:
    for context in contexts:
        context.stop()


@pytest.mark.asyncio
async def test_finalize_call_with_tool_outcome_sets_completed_status() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="Call.", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(outcome={"status": "achieved", "reason": "Done."})

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch("app.modules.webhooks.realtime_ws._generate_llm_summary",
                   AsyncMock(return_value="summary")):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert task.status == TaskStatus.COMPLETED
    assert task.summary == "summary"
    mocks["log_line_repo"].create_many.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_call_with_tool_outcome_failed_sets_error_reason() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(
        outcome={"status": "rejected", "reason": "User declined."},
    )

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch("app.modules.webhooks.realtime_ws._generate_llm_summary",
                   AsyncMock(return_value="")):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert task.status == TaskStatus.FAILED
    assert task.error_reason == "User declined."


@pytest.mark.asyncio
async def test_finalize_call_no_outcome_classifies_from_transcript() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="Get info.", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(outcome=None)

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch(
            "app.modules.webhooks.realtime_ws._classify_outcome_from_transcript",
            AsyncMock(return_value={"status": "achieved", "reason": "Inferred."}),
        ), patch(
            "app.modules.webhooks.realtime_ws._generate_llm_summary",
            AsyncMock(return_value="summary"),
        ):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_finalize_call_no_outcome_and_classification_fails_marks_failed() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(outcome=None)

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch(
            "app.modules.webhooks.realtime_ws._classify_outcome_from_transcript",
            AsyncMock(return_value=None),
        ), patch(
            "app.modules.webhooks.realtime_ws._generate_llm_summary",
            AsyncMock(return_value=""),
        ):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert task.status == TaskStatus.FAILED
    assert "Call ended without outcome" in task.error_reason


@pytest.mark.asyncio
async def test_finalize_call_tags_error_reason_when_bridge_init_failed() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(outcome=None)
    bridge.init_failed = True

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch("app.modules.webhooks.realtime_ws._classify_outcome_from_transcript",
                   AsyncMock(return_value=None)), \
             patch("app.modules.webhooks.realtime_ws._generate_llm_summary",
                   AsyncMock(return_value="")):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert task.status == TaskStatus.FAILED
    assert task.error_reason.startswith("[REALTIME_INIT_FAILED]")


@pytest.mark.asyncio
async def test_finalize_call_persists_token_usage_to_call_session() -> None:
    task = Task(
        id=42, target_phone="+37360000001", status=TaskStatus.IN_PROGRESS,
        template_id=5, user_id=7, slot_data={},
    )
    template = DialogTemplate(
        id=5, name="T", base_script="x", required_slots=[], language="en", is_active=True,
    )
    call_session = CallSession(id=1, task_id=42, start_time=datetime.now())
    mocks = _build_finalize_mocks(task, template, call_session)
    bridge = _make_bridge_with_transcript(outcome={"status": "achieved", "reason": "Done."})
    bridge.input_audio_tokens = 123
    bridge.output_audio_tokens = 456
    bridge.input_text_tokens = 7
    bridge.output_text_tokens = 8

    contexts = _patch_finalize_dependencies(mocks)
    try:
        with patch("app.modules.webhooks.realtime_ws._generate_llm_summary",
                   AsyncMock(return_value="summary")):
            await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    assert call_session.input_audio_tokens == 123
    assert call_session.output_audio_tokens == 456
    assert call_session.input_text_tokens == 7
    assert call_session.output_text_tokens == 8


@pytest.mark.asyncio
async def test_finalize_call_task_missing_returns_early() -> None:
    mocks = _build_finalize_mocks(task=None, template=None, call_session=None)
    bridge = _make_bridge_with_transcript()

    contexts = _patch_finalize_dependencies(mocks)
    try:
        await _finalize_call(bridge)
    finally:
        _stop_patches(contexts)

    mocks["task_repo"].update.assert_not_called()
    mocks["log_line_repo"].create_many.assert_not_called()
