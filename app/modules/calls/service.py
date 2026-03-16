from typing import Annotated

from fastapi import Depends

from app.core.logging import get_logger
from app.modules.calls.exceptions import CallSessionNotFoundError
from app.modules.calls.models import CallSession
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.calls.schema import (
    CallSessionResponse,
    LogLineResponse,
    TranscriptResponse,
)
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.repository import TaskRepository

logger = get_logger(__name__)

# In-memory cache for generated demo audio (task_id → (bytes, content_type))
_demo_audio_cache: dict[int, tuple[bytes, str]] = {}


class CallService:
    def __init__(
        self,
        call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
        log_line_repository: Annotated[LogLineRepository, Depends(LogLineRepository)],
        task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
    ) -> None:
        self.call_session_repository = call_session_repository
        self.log_line_repository = log_line_repository
        self.task_repository = task_repository

    async def get_transcript(self, task_id: int, user_id: int, is_admin: bool = False) -> TranscriptResponse:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")

        call_session = await self.call_session_repository.get_by_task_id(task_id)
        if not call_session:
            raise CallSessionNotFoundError(f"No call session found for task {task_id}")

        log_lines = await self.log_line_repository.get_by_session_id(call_session.id)

        return TranscriptResponse(
            session=CallSessionResponse(
                id=call_session.id,
                task_id=call_session.task_id,
                start_time=call_session.start_time,
                duration=call_session.duration,
                recording_uri=call_session.recording_uri,
                created_at=call_session.created_at,
                updated_at=call_session.updated_at,
            ),
            lines=[
                LogLineResponse(
                    id=line.id,
                    session_id=line.session_id,
                    timestamp=line.timestamp,
                    speaker=line.speaker,
                    text=line.text,
                    detected_intent=line.detected_intent,
                )
                for line in log_lines
            ],
        )

    async def get_session_by_task(self, task_id: int, user_id: int, is_admin: bool = False) -> CallSession:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise TaskNotFoundError(f"Task with id {task_id} not found")

        call_session = await self.call_session_repository.get_by_task_id(task_id)
        if not call_session:
            raise CallSessionNotFoundError(f"No call session found for task {task_id}")

        return call_session

    async def get_recording_audio(self, task_id: int, user_id: int, is_admin: bool = False) -> tuple[bytes, str]:
        """Return (audio_bytes, content_type) for the call recording."""
        session = await self.get_session_by_task(task_id, user_id, is_admin=is_admin)
        if not session.recording_uri:
            raise ValueError(f"No recording available for task {task_id}")

        # Try to fetch from Twilio first
        try:
            from app.integrations.twilio_adapter import TwilioAdapter

            adapter = TwilioAdapter()
            audio = await adapter.get_recording_audio(session.recording_uri)
            return audio, "audio/wav"
        except Exception:
            logger.warning(
                "Could not fetch recording from Twilio for task %d, generating demo audio from transcript",
                task_id,
            )

        # Return cached demo audio if available
        if task_id in _demo_audio_cache:
            logger.debug("Serving cached demo audio for task %d", task_id)
            return _demo_audio_cache[task_id]

        # Fallback: generate speech from transcript lines using TTS
        from app.core.audio import generate_demo_conversation_mp3_async, generate_demo_wav

        log_lines = await self.log_line_repository.get_by_session_id(session.id)
        if log_lines:
            lines = [
                ("Agent" if line.speaker.value == "agent" else "Caller", line.text)
                for line in log_lines
            ]
            logger.info("Generating TTS for task %d with %d lines", task_id, len(lines))
            try:
                audio = await generate_demo_conversation_mp3_async(lines)
            except Exception:
                logger.exception("TTS generation failed for task %d", task_id)
                audio = b""

            if audio and not audio[:4].startswith(b"RIFF"):
                logger.info("TTS succeeded for task %d: %d bytes MP3", task_id, len(audio))
                _demo_audio_cache[task_id] = (audio, "audio/mpeg")
                return audio, "audio/mpeg"
            else:
                logger.warning(
                    "TTS returned WAV fallback for task %d (%d bytes, header=%s)",
                    task_id,
                    len(audio) if audio else 0,
                    audio[:4].hex() if audio else "empty",
                )

        duration = session.duration or 5
        result = generate_demo_wav(duration_seconds=min(duration, 30)), "audio/wav"
        _demo_audio_cache[task_id] = result
        return result
