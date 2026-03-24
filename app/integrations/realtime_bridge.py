"""Bridges a Twilio Media Stream WebSocket to OpenAI Realtime API.

One RealtimeBridge instance owns a single active call's audio pipeline.
Twilio WS ⇄ OpenAI Realtime WS — μ-law 8kHz passthrough both directions.
"""

import asyncio
import contextlib
import json
from collections import deque
from datetime import datetime
from typing import Any

import websockets
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ws_manager import call_broadcaster
from app.integrations.twilio_adapter import TwilioAdapter
from app.modules.calls.schema import Speaker

logger = get_logger(__name__)

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model={model}"

IDLE_TIMEOUT_SECONDS = 10.0
MAX_SILENCE_NUDGES = 3
HANGUP_DRAIN_TIMEOUT_SECONDS = 15.0
HANGUP_POST_DRAIN_BUFFER_SECONDS = 1.0
MARK_DRAIN_POLL_INTERVAL_SECONDS = 0.2
AUDIO_CHUNK_LOG_THRESHOLDS = (1, 50, 250, 500)
TRANSCRIPT_LOG_MAX_CHARS = 200

LANG_DISPLAY_NAMES = {"en": "English", "ru": "Russian", "ro": "Romanian"}

NUDGE_PHRASES = {
    "en": "Sorry, I didn't catch that. Could you repeat?",
    "ru": "Извините, я не расслышал. Можете повторить?",
    "ro": "Scuze, nu v-am auzit bine. Puteți repeta?",
}

RETRY_LATER_PHRASES = {
    "en": "I seem to be having trouble hearing you. I'll try to call back later. Goodbye.",
    "ru": "Похоже, я вас не слышу. Перезвоню позже. До свидания.",
    "ro": "Se pare că nu vă aud bine. Voi încerca să revin mai târziu. La revedere.",
}

REPORT_OUTCOME_TOOL = {
    "type": "function",
    "name": "report_outcome",
    "description": (
        "Call this EXACTLY ONCE when the conversation objective is resolved, BEFORE saying goodbye. "
        "Use status='achieved' if the goal was met, 'failed' if it clearly cannot be met, "
        "'rejected' if the other party refused."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["achieved", "failed", "rejected"]},
            "reason": {"type": "string", "description": "One-sentence rationale"},
        },
        "required": ["status", "reason"],
    },
}


class RealtimeBridge:
    def __init__(
        self,
        twilio_ws: WebSocket,
        task_id: int,
        user_id: int,
        language: str,
        system_prompt: str,
    ) -> None:
        self.twilio_ws = twilio_ws
        self.task_id = task_id
        self.user_id = user_id
        self.language = language
        self.system_prompt = system_prompt

        self.openai_ws: websockets.WebSocketClientProtocol | None = None
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.stream_start_time: datetime | None = None

        self.latest_media_timestamp: int = 0
        self.response_start_timestamp_twilio: int | None = None
        self.last_assistant_item_id: str | None = None
        self.mark_queue: deque[str] = deque()
        self._mark_counter = 0

        self.transcript_buffer: list[dict[str, Any]] = []
        self._current_agent_text: str = ""
        self._current_user_text: str = ""
        self.outcome: dict[str, str] | None = None

        self._twilio_chunks_received: int = 0
        self._openai_chunks_sent: int = 0
        self._hangup_pending: bool = False

        self._idle_timer: asyncio.Task | None = None
        self._silence_nudges: int = 0

    async def run(self) -> None:
        logger.info("[task=%d] RealtimeBridge starting (lang=%s)", self.task_id, self.language)
        try:
            openai_url = OPENAI_REALTIME_URL.format(model=settings.OPENAI_REALTIME_MODEL)
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            logger.info("[task=%d] Connecting to OpenAI Realtime: %s", self.task_id, openai_url)
            async with websockets.connect(openai_url, additional_headers=headers) as openai_ws:
                self.openai_ws = openai_ws
                logger.info("[task=%d] OpenAI WS connected", self.task_id)
                await self._init_openai_session()

                twilio_task = asyncio.create_task(self._twilio_to_openai())
                openai_task = asyncio.create_task(self._openai_to_twilio())
                done, pending = await asyncio.wait(
                    {twilio_task, openai_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for pending_task in pending:
                    pending_task.cancel()
                for pending_task in pending:
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await pending_task
                logger.info("[task=%d] Both bridge loops finished", self.task_id)
        except websockets.exceptions.ConnectionClosed as websocket_closed_error:
            close_code = getattr(websocket_closed_error, "code", "?")
            close_reason = getattr(websocket_closed_error, "reason", "?")
            logger.info("[task=%d] OpenAI WS closed: code=%s reason=%s",
                        self.task_id, close_code, close_reason)
        except Exception:
            logger.exception("[task=%d] RealtimeBridge failed", self.task_id)
        finally:
            self._cancel_idle_timer()
            logger.info(
                "[task=%d] Bridge finished. Twilio chunks in=%d, OpenAI audio out=%d, transcript lines=%d, outcome=%s",
                self.task_id, self._twilio_chunks_received, self._openai_chunks_sent,
                len(self.transcript_buffer), self.outcome,
            )

    async def _init_openai_session(self) -> None:
        turn_detection: dict[str, Any]
        if settings.REALTIME_VAD_MODE == "semantic_vad":
            turn_detection = {
                "type": "semantic_vad",
                "eagerness": settings.REALTIME_VAD_EAGERNESS,
                "create_response": True,
                "interrupt_response": True,
            }
        else:
            turn_detection = {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                "create_response": True,
                "interrupt_response": True,
            }

        session_update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": settings.OPENAI_REALTIME_MODEL,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "turn_detection": turn_detection,
                        "transcription": {"model": "whisper-1"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": settings.OPENAI_REALTIME_VOICE,
                    },
                },
                "instructions": self.system_prompt,
                "tools": [REPORT_OUTCOME_TOOL],
                "tool_choice": "auto",
            },
        }
        await self.openai_ws.send(json.dumps(session_update))
        logger.info(
            "[task=%d] OpenAI session.update sent: model=%s voice=%s vad=%s lang=%s",
            self.task_id, settings.OPENAI_REALTIME_MODEL, settings.OPENAI_REALTIME_VOICE,
            turn_detection.get("type"), self.language,
        )

        await self._trigger_initial_response()
        logger.info("[task=%d] Initial response.create triggered (AI should speak first)", self.task_id)

    async def _trigger_initial_response(self) -> None:
        """For outbound calls, the AI must speak first — prompt it explicitly.

        We do NOT set per-response instructions here: they would OVERRIDE the full
        session prompt (name, language, objective, slot_data). A bare response.create
        makes the model use the session instructions, which already contain everything.
        """
        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    async def _twilio_to_openai(self) -> None:
        try:
            async for raw_message in self.twilio_ws.iter_text():
                message = json.loads(raw_message)
                event_name = message.get("event")

                if event_name == "start":
                    start_data = message.get("start", {})
                    self.stream_sid = start_data.get("streamSid")
                    self.call_sid = start_data.get("callSid")
                    self.stream_start_time = datetime.now()
                    logger.info(
                        "[task=%d] Media stream started: streamSid=%s callSid=%s",
                        self.task_id, self.stream_sid, self.call_sid,
                    )
                    await self._emit("call_answered")

                elif event_name == "media":
                    self.latest_media_timestamp = int(message["media"].get("timestamp", 0))
                    audio_payload = message["media"]["payload"]
                    if self.openai_ws and self.openai_ws.state == websockets.protocol.State.OPEN:
                        await self.openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": audio_payload,
                        }))
                    self._twilio_chunks_received += 1
                    if self._twilio_chunks_received in AUDIO_CHUNK_LOG_THRESHOLDS:
                        logger.info("[task=%d] Twilio audio chunks received: %d",
                                    self.task_id, self._twilio_chunks_received)

                elif event_name == "mark":
                    if self.mark_queue:
                        self.mark_queue.popleft()

                elif event_name == "stop":
                    logger.info("[task=%d] Media stream stopped (Twilio sent stop event)", self.task_id)
                    break

                else:
                    logger.debug("[task=%d] Unhandled Twilio event: %s", self.task_id, event_name)

        except Exception:
            logger.exception("[task=%d] Twilio→OpenAI loop failed", self.task_id)

    async def _openai_to_twilio(self) -> None:
        try:
            async for raw_message in self.openai_ws:
                event = json.loads(raw_message)
                event_type = event.get("type", "")

                if event_type == "response.output_audio.delta":
                    await self._forward_audio_to_twilio(event)

                elif event_type == "response.output_audio_transcript.delta":
                    self._current_agent_text += event.get("delta", "")

                elif event_type == "response.output_audio_transcript.done":
                    agent_text = (event.get("transcript") or self._current_agent_text).strip()
                    if agent_text:
                        self._record_transcript(Speaker.AGENT, agent_text)
                        await self._emit("message", {"speaker": "agent", "text": agent_text})
                        logger.info("[task=%d] AGENT: %s", self.task_id, agent_text[:TRANSCRIPT_LOG_MAX_CHARS])
                    self._current_agent_text = ""

                elif event_type == "conversation.item.input_audio_transcription.delta":
                    self._current_user_text += event.get("delta", "")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    user_text = (event.get("transcript") or self._current_user_text).strip()
                    if user_text:
                        self._record_transcript(Speaker.INTERLOCUTOR, user_text)
                        await self._emit("message", {"speaker": "interlocutor", "text": user_text})
                        logger.info("[task=%d] USER: %s", self.task_id, user_text[:TRANSCRIPT_LOG_MAX_CHARS])
                    self._current_user_text = ""

                elif event_type == "input_audio_buffer.speech_started":
                    logger.debug("[task=%d] User speech started (possible barge-in)", self.task_id)
                    self._cancel_idle_timer()
                    self._silence_nudges = 0
                    await self._handle_barge_in()

                elif event_type == "response.output_item.added":
                    response_item = event.get("item", {})
                    if response_item.get("type") == "message" and response_item.get("role") == "assistant":
                        self.last_assistant_item_id = response_item.get("id")

                elif event_type == "response.function_call_arguments.done":
                    await self._handle_function_call(event)

                elif event_type == "error":
                    error_details = event.get("error", {})
                    logger.error(
                        "[task=%d] OpenAI Realtime ERROR: type=%s code=%s message=%s",
                        self.task_id,
                        error_details.get("type"),
                        error_details.get("code"),
                        error_details.get("message"),
                    )

                elif event_type == "session.created":
                    logger.info("[task=%d] OpenAI session.created received", self.task_id)

                elif event_type == "session.updated":
                    logger.info("[task=%d] OpenAI session.updated (config applied)", self.task_id)

                elif event_type == "response.done":
                    response_status = event.get("response", {}).get("status")
                    logger.debug("[task=%d] response.done status=%s", self.task_id, response_status)

                elif event_type == "response.output_audio.done":
                    if self._hangup_pending:
                        self._hangup_pending = False
                        logger.info("[task=%d] Farewell audio sent, scheduling hangup", self.task_id)
                        asyncio.create_task(self._hangup_after_drain())
                    else:
                        self._start_idle_timer()

        except Exception:
            logger.exception("[task=%d] OpenAI→Twilio loop failed", self.task_id)

    async def _forward_audio_to_twilio(self, event: dict[str, Any]) -> None:
        if not self.stream_sid:
            return
        if self.twilio_ws.client_state != WebSocketState.CONNECTED:
            return

        payload = event.get("delta", "")
        if not payload:
            return

        await self.twilio_ws.send_json({
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": payload},
        })
        self._openai_chunks_sent += 1
        if self._openai_chunks_sent in AUDIO_CHUNK_LOG_THRESHOLDS:
            logger.info("[task=%d] OpenAI audio chunks sent to Twilio: %d",
                        self.task_id, self._openai_chunks_sent)

        if self.response_start_timestamp_twilio is None:
            self.response_start_timestamp_twilio = self.latest_media_timestamp
            item_id = event.get("item_id")
            if item_id:
                self.last_assistant_item_id = item_id

        self._mark_counter += 1
        mark_name = f"resp-{self._mark_counter}"
        await self.twilio_ws.send_json({
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {"name": mark_name},
        })
        self.mark_queue.append(mark_name)

    async def _handle_barge_in(self) -> None:
        if not self.last_assistant_item_id or self.response_start_timestamp_twilio is None:
            return

        elapsed_ms = self.latest_media_timestamp - self.response_start_timestamp_twilio
        if elapsed_ms <= 0:
            elapsed_ms = 0

        try:
            await self.openai_ws.send(json.dumps({
                "type": "conversation.item.truncate",
                "item_id": self.last_assistant_item_id,
                "content_index": 0,
                "audio_end_ms": elapsed_ms,
            }))
        except Exception:
            logger.exception("Failed to truncate on barge-in for task %d", self.task_id)

        if self.stream_sid and self.twilio_ws.client_state == WebSocketState.CONNECTED:
            await self.twilio_ws.send_json({"event": "clear", "streamSid": self.stream_sid})

        self.mark_queue.clear()
        self.response_start_timestamp_twilio = None
        self.last_assistant_item_id = None

    async def _handle_function_call(self, event: dict[str, Any]) -> None:
        name = event.get("name")
        call_id = event.get("call_id")
        arguments_raw = event.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_raw)
        except json.JSONDecodeError:
            arguments = {}

        if name == "report_outcome":
            self.outcome = {
                "status": arguments.get("status", "failed"),
                "reason": arguments.get("reason", ""),
            }
            logger.info("[task=%d] Outcome reported via tool: %s", self.task_id, self.outcome)

            await self.openai_ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({"acknowledged": True}),
                },
            }))
            self._hangup_pending = True
            lang_name = LANG_DISPLAY_NAMES.get(self.language, "English")
            await self.openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": f"Speak ONLY in {lang_name}. Say a brief goodbye and end the call.",
                },
            }))
            logger.info("[task=%d] Triggered farewell response; hangup queued", self.task_id)

    def _start_idle_timer(self, timeout_seconds: float = IDLE_TIMEOUT_SECONDS) -> None:
        self._cancel_idle_timer()
        self._idle_timer = asyncio.create_task(self._handle_idle_timeout(timeout_seconds))

    def _cancel_idle_timer(self) -> None:
        if self._idle_timer and not self._idle_timer.done():
            self._idle_timer.cancel()
        self._idle_timer = None

    async def _handle_idle_timeout(self, timeout_seconds: float) -> None:
        try:
            await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            return

        if not self.openai_ws or self.openai_ws.state != websockets.protocol.State.OPEN:
            return

        self._silence_nudges += 1
        logger.info("[task=%d] Idle for %ss — nudge #%d",
                    self.task_id, timeout_seconds, self._silence_nudges)

        lang_name = LANG_DISPLAY_NAMES.get(self.language, "English")
        nudge_phrase = NUDGE_PHRASES.get(self.language, NUDGE_PHRASES["en"])
        retry_later_phrase = RETRY_LATER_PHRASES.get(self.language, RETRY_LATER_PHRASES["en"])

        if self._silence_nudges >= MAX_SILENCE_NUDGES:
            logger.info("[task=%d] %d silent nudges — forcing failed outcome + hangup",
                        self.task_id, MAX_SILENCE_NUDGES)
            self.outcome = {
                "status": "failed",
                "reason": "No response from the interlocutor after multiple attempts.",
            }
            self._hangup_pending = True
            await self.openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": (
                        f"Speak ONLY in {lang_name}. Say exactly this (translated naturally "
                        f"into {lang_name} if needed): \"{retry_later_phrase}\""
                    ),
                },
            }))
            return

        await self.openai_ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "instructions": (
                    f"Speak ONLY in {lang_name}. The other person hasn't replied. "
                    f"Say exactly this in {lang_name}: \"{nudge_phrase}\" "
                    "Do NOT repeat your original question or introduction."
                ),
            },
        }))

    async def _hangup_after_drain(self) -> None:
        """Wait for Twilio's audio buffer to drain (marks to clear), then hang up the call."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + HANGUP_DRAIN_TIMEOUT_SECONDS
        while self.mark_queue and loop.time() < deadline:  # noqa: ASYNC110
            await asyncio.sleep(MARK_DRAIN_POLL_INTERVAL_SECONDS)
        await asyncio.sleep(HANGUP_POST_DRAIN_BUFFER_SECONDS)

        if not self.call_sid:
            logger.warning("[task=%d] Cannot hang up: call_sid unknown", self.task_id)
            return
        try:
            await TwilioAdapter().hangup(self.call_sid)
            logger.info("[task=%d] Twilio call hung up after farewell", self.task_id)
        except Exception:
            logger.exception("[task=%d] Failed to hang up Twilio call", self.task_id)

    def _record_transcript(self, speaker: Speaker, text: str) -> None:
        self.transcript_buffer.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now(),
        })

    async def _emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        if call_broadcaster.has_listeners(self.task_id):
            await call_broadcaster.emit(self.task_id, event, data)
