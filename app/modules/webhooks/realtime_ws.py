"""FastAPI WebSocket endpoint for Twilio Media Streams.

Twilio opens this WS after the <Connect><Stream> TwiML runs. We receive
start/media/stop events, spin up a RealtimeBridge that also connects to
OpenAI Realtime, and bridge audio both ways. On stop we finalize the
call (persist transcript, set task status, trigger post-call).
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import async_session
from app.core.logging import get_logger
from app.core.ws_manager import call_broadcaster
from app.integrations.openai_adapter import OpenAIAdapter
from app.integrations.prompt_builder import PromptBuilder
from app.integrations.realtime_bridge import RealtimeBridge
from app.integrations.twilio_adapter import TwilioAdapter
from app.modules.calls.models import LogLine
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.calls.schema import Speaker
from app.modules.notifications.post_call import PostCallProcessor
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.repository import TemplateRepository
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

router = APIRouter(tags=["realtime"])

SUMMARY_FALLBACK_MAX_CHARS = 500
VALID_OUTCOME_STATUSES = ("achieved", "deferred", "failed", "rejected")


@router.websocket("/ws/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    client = websocket.client
    host = client.host if client else "?"
    port = client.port if client else "?"
    logger.info("Twilio Media Stream WS: accept from %s:%s", host, port)
    await websocket.accept()

    params = await _wait_for_start(websocket)
    if params is None:
        logger.warning("Twilio Media Stream WS: no valid start event received, closing")
        await websocket.close()
        return

    task_id = params["task_id"]
    user_id = params["user_id"]
    language = params["language"]
    start_event = params["start_event"]

    prompt_result = await _build_system_prompt_for_task(task_id, language)
    if prompt_result is None:
        logger.error("[task=%d] Cannot build system prompt (task or template missing)", task_id)
        await websocket.close()
        return
    system_prompt, transcription_hint = prompt_result

    stream_sid = start_event.get("start", {}).get("streamSid")
    call_sid = start_event.get("start", {}).get("callSid")
    logger.info(
        "[task=%d] WS start event parsed: stream_sid=%s call_sid=%s lang=%s prompt_len=%d hint_len=%d",
        task_id,
        stream_sid,
        call_sid,
        language,
        len(system_prompt),
        len(transcription_hint),
    )

    bridge = RealtimeBridge(
        twilio_ws=websocket,
        task_id=task_id,
        user_id=user_id,
        language=language,
        system_prompt=system_prompt,
        transcription_hint=transcription_hint,
    )
    bridge.stream_sid = stream_sid
    bridge.call_sid = call_sid
    bridge.stream_start_time = datetime.now()

    try:
        await bridge.run()
    except WebSocketDisconnect:
        logger.info("[task=%d] Twilio WS disconnected", task_id)
    except Exception:
        logger.exception("[task=%d] Realtime bridge error", task_id)
    finally:
        logger.info("[task=%d] Finalizing call", task_id)
        await _finalize_call(bridge)
        logger.info("[task=%d] Call finalized", task_id)


TRANSCRIPTION_HINT_MAX_CHARS = 500


def _build_transcription_hint(slot_data: dict[str, str], assistant_name: str | None) -> str:
    """Build a Whisper/gpt-4o-transcribe prompt hint from proper-noun-like slot values.

    Only single-token, capitalized or digit-leading values ≤ 30 chars are included.
    Multi-word descriptive phrases are excluded because Whisper-family models echo
    long prompts back as "transcription" when the audio is silent or unintelligible,
    leaking task inputs into the interlocutor's transcript.
    """
    fragments: list[str] = []
    if assistant_name:
        fragments.append(assistant_name)
    for value in slot_data.values():
        if not isinstance(value, str):
            continue
        v = value.strip()
        if not v or len(v) > 30 or " " in v:
            continue
        if not (v[0].isupper() or v[0].isdigit()):
            continue
        fragments.append(v)
    if not fragments:
        return ""
    hint = ", ".join(fragments)
    return hint[:TRANSCRIPTION_HINT_MAX_CHARS]


async def _build_system_prompt_for_task(task_id: int, language: str) -> tuple[str, str] | None:
    """Rebuild system prompt + transcription hint server-side from the DB.

    The prompt is too long to fit in TwiML <Parameter> (Twilio caps TwiML at 4000
    chars), so we pass only task_id via TwiML and reconstruct the prompt here.
    Returns None if the task or template cannot be loaded; otherwise a tuple of
    (system_prompt, transcription_hint).
    """
    async with async_session() as session:
        task_repo = TaskRepository(session=session)
        template_repo = TemplateRepository(session=session)
        call_session_repo = CallSessionRepository(session=session)
        log_line_repo = LogLineRepository(session=session)
        user_repo = UserRepository(session=session)

        task = await task_repo.get_by_id_any_user(task_id)
        if not task:
            return None
        template = await template_repo.get_by_id(task.template_id)
        if not template:
            return None

        owner = await user_repo.get_by_id(task.user_id)
        assistant_name = owner.assistant_name if owner else None

        prior_context = None
        call_session = await call_session_repo.get_by_task_id(task_id)
        if call_session:
            log_lines = await log_line_repo.get_by_session_id(call_session.id)
            if log_lines:
                formatted_lines = [
                    f"{'Agent' if line.speaker == Speaker.AGENT else 'Interlocutor'}: {line.text}" for line in log_lines
                ]
                prior_context = "\n".join(formatted_lines[-20:])

        system_prompt = PromptBuilder.build_system_prompt(
            template.base_script,
            task.slot_data,
            language,
            use_function_tool=True,
            require_ai_disclosure=settings.AI_DISCLOSURE_REQUIRED,
            prior_attempt_context=prior_context,
            assistant_name=assistant_name,
        )
        transcription_hint = _build_transcription_hint(task.slot_data, assistant_name)
        return system_prompt, transcription_hint


async def _wait_for_start(websocket: WebSocket) -> dict[str, Any] | None:
    """Wait for the 'start' event from Twilio and extract custom parameters."""
    try:
        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            event_name = message.get("event")
            if event_name == "connected":
                continue
            if event_name == "start":
                custom_parameters = message.get("start", {}).get("customParameters", {}) or {}
                task_id_str = custom_parameters.get("task_id")
                user_id_str = custom_parameters.get("user_id")
                if not task_id_str or not user_id_str:
                    logger.error("Missing task_id or user_id in stream start params")
                    return None
                return {
                    "task_id": int(task_id_str),
                    "user_id": int(user_id_str),
                    "language": custom_parameters.get("language", "en"),
                    "start_event": message,
                }
            logger.warning("Unexpected event before start: %s", event_name)
    except WebSocketDisconnect:
        logger.info("Twilio WS disconnected before start")
        return None
    except Exception:
        logger.exception("Failed to parse Twilio start event")
        return None


def _format_transcript_as_conversation(transcript: list[dict[str, Any]]) -> str:
    """Format a transcript buffer as 'Speaker: text' newline-delimited text."""
    lines = []
    for entry in transcript:
        speaker_label = "Agent" if entry["speaker"] == Speaker.AGENT else "Interlocutor"
        lines.append(f"{speaker_label}: {entry['text']}")
    return "\n".join(lines)


async def _finalize_call(bridge: RealtimeBridge) -> None:
    """Persist transcript, set task status, trigger post-call processing."""
    async with async_session() as session:
        task_repo = TaskRepository(session=session)
        template_repo = TemplateRepository(session=session)
        call_session_repo = CallSessionRepository(session=session)
        log_line_repo = LogLineRepository(session=session)
        user_repo = UserRepository(session=session)

        task = await task_repo.get_by_id_any_user(bridge.task_id)
        if not task:
            logger.error("Task %d missing at finalize", bridge.task_id)
            return

        call_session = await call_session_repo.get_by_task_id(bridge.task_id)

        ordered_transcript = bridge.get_ordered_transcript()
        if ordered_transcript and call_session:
            log_lines = [
                LogLine(
                    session_id=call_session.id,
                    timestamp=entry["timestamp"],
                    speaker=entry["speaker"],
                    text=entry["text"],
                )
                for entry in ordered_transcript
            ]
            await log_line_repo.create_many(log_lines)

        if call_session and bridge.stream_start_time:
            duration_seconds = int((datetime.now() - bridge.stream_start_time).total_seconds())
            if not call_session.duration:
                call_session.duration = duration_seconds
            if not call_session.recording_uri and bridge.call_sid:
                try:
                    call_session.recording_uri = await TwilioAdapter().get_recording_url(bridge.call_sid)
                except Exception:
                    logger.exception("Failed to fetch recording URL for task %d", bridge.task_id)
            call_session.input_audio_tokens = bridge.input_audio_tokens
            call_session.output_audio_tokens = bridge.output_audio_tokens
            call_session.input_text_tokens = bridge.input_text_tokens
            call_session.output_text_tokens = bridge.output_text_tokens
            await call_session_repo.update(call_session)

        outcome = bridge.outcome
        if not outcome and ordered_transcript and task:
            template = await template_repo.get_by_id(task.template_id)
            objective = template.base_script if template else ""
            outcome = await _classify_outcome_from_transcript(
                ordered_transcript,
                bridge.language,
                objective,
            )
            if outcome:
                logger.info("[task=%d] Inferred outcome from transcript: %s", bridge.task_id, outcome)

        if outcome:
            status_str = outcome.get("status", "failed")
            if status_str == "achieved":
                task.status = TaskStatus.COMPLETED
            elif status_str == "deferred":
                task.status = TaskStatus.DEFERRED
                task.error_reason = outcome.get("reason") or "Follow-up needed — objective not achievable this call"
            else:
                task.status = TaskStatus.FAILED
                task.error_reason = outcome.get("reason") or "Objective not achieved"
        else:
            task.status = TaskStatus.FAILED
            task.error_reason = task.error_reason or "Call ended without outcome"

        if bridge.init_failed:
            task.error_reason = f"[REALTIME_INIT_FAILED] {task.error_reason or 'OpenAI Realtime connection failed'}"

        task.summary = await _generate_llm_summary(ordered_transcript, bridge.language)
        await task_repo.update(task)

        if call_broadcaster.has_listeners(bridge.task_id):
            await call_broadcaster.emit(
                bridge.task_id,
                "call_ended",
                {
                    "status": task.status,
                    "summary": task.summary,
                    "error_reason": task.error_reason,
                },
            )

        post_call = PostCallProcessor(
            task_repository=task_repo,
            user_repository=user_repo,
            call_session_repository=call_session_repo,
            log_line_repository=log_line_repo,
            template_repository=template_repo,
        )
        try:
            await post_call.process(task)
        except Exception:
            logger.exception("Post-call processing failed for task %d", bridge.task_id)


async def _classify_outcome_from_transcript(
    transcript: list[dict[str, Any]],
    language: str,
    objective: str,
) -> dict[str, str] | None:
    """Ask the LLM to classify whether the call objective was achieved, given the transcript.

    Used when the AI didn't call report_outcome before the interlocutor hung up.
    Returns {'status': 'achieved'|'failed'|'rejected', 'reason': '...'} or None on error.
    """
    conversation_text = _format_transcript_as_conversation(transcript)

    system_prompt = (
        "You are an evaluator. Given a phone call transcript and the caller's objective, "
        "decide the outcome. Respond with a SINGLE JSON object, no prose, "
        f"with keys 'status' and 'reason' (one short sentence in {language}).\n"
        "'status' must be one of:\n"
        "  - 'achieved': the objective was fully met (booking confirmed, info obtained, etc.)\n"
        "  - 'deferred': the conversation was productive but the objective was NOT met and needs "
        "a follow-up (e.g., no slots this week — told to call back, record exists but only an "
        "alternative time was offered, partner will get back to the caller).\n"
        "  - 'failed': hard failure (wrong number, record not found, voicemail, unintelligible, "
        "technical error).\n"
        "  - 'rejected': the other party refused explicitly (opt-out, remove from list)."
    )
    user_message = f"OBJECTIVE:\n{objective}\n\nTRANSCRIPT:\n{conversation_text}"

    try:
        llm = OpenAIAdapter()
        raw_response = await llm.generate_response(
            [{"role": "user", "content": user_message}],
            system_prompt,
        )
        raw_response = raw_response.strip()
        if raw_response.startswith("```"):
            raw_response = raw_response.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        classification = json.loads(raw_response)
        status = str(classification.get("status", "")).lower()
        if status not in VALID_OUTCOME_STATUSES:
            return None
        return {"status": status, "reason": str(classification.get("reason", ""))}
    except Exception:
        logger.exception("Outcome classification from transcript failed")
        return None


async def _generate_llm_summary(transcript: list[dict[str, Any]], language: str) -> str:
    """Generate a 2-3 sentence summary via LLM in the call's language."""
    if not transcript:
        return ""

    conversation_text = _format_transcript_as_conversation(transcript)

    try:
        llm = OpenAIAdapter()
        return await llm.generate_response(
            [{"role": "user", "content": f"Conversation:\n{conversation_text}"}],
            PromptBuilder.build_summary_prompt(language),
        )
    except Exception:
        logger.exception("LLM summary generation failed; falling back to truncated transcript")
        return conversation_text[:SUMMARY_FALLBACK_MAX_CHARS]
