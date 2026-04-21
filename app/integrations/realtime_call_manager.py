"""Call manager for the OpenAI Realtime + Twilio Media Streams path.

Drop-in replacement for CallManager when settings.USE_REALTIME_API is True.
Initiates the outbound call with <Connect><Stream> TwiML. Audio and dialog
happen inside the /ws/media-stream WebSocket handler, not here.
"""

from datetime import datetime
from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ws_manager import call_broadcaster
from app.integrations.twilio_adapter import TwilioAdapter
from app.modules.calls.models import CallSession
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.repository import TemplateRepository
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

DEFAULT_LANGUAGE = "en"


class RealtimeCallManager:
    def __init__(
        self,
        task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
        template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
        call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
        log_line_repository: Annotated[LogLineRepository, Depends(LogLineRepository)],
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
    ) -> None:
        self.task_repository = task_repository
        self.template_repository = template_repository
        self.call_session_repository = call_session_repository
        self.log_line_repository = log_line_repository
        self.user_repository = user_repository
        self._voice = TwilioAdapter()

    async def execute_task(self, task_id: int, user_id: int, is_admin: bool = False) -> Task:
        if is_admin:
            task = await self.task_repository.get_by_id_any_user(task_id)
        else:
            task = await self.task_repository.get_by_id(task_id, user_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status not in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
            raise ValueError(f"Task {task_id} cannot be executed (status: {task.status})")

        template = await self.template_repository.get_by_id(task.template_id)
        if not template:
            raise ValueError(f"Template {task.template_id} not found")
        if not template.is_active:
            raise ValueError(
                f"Template {task.template_id} is deactivated — cannot execute scheduled task"
            )

        claimed = await self.task_repository.claim_for_execution(task_id)
        if not claimed:
            raise ValueError(f"Task {task_id} is already being executed by another worker")
        task.status = TaskStatus.IN_PROGRESS

        language = template.language or DEFAULT_LANGUAGE
        dial_phone = self._resolve_phone(task.target_phone)
        logger.info(
            "[task=%d] Executing realtime call: target=%s dial=%s template=%s lang=%s",
            task.id,
            task.target_phone,
            dial_phone,
            template.name,
            language,
        )

        await self._emit(task_id, "status_change", {"status": TaskStatus.IN_PROGRESS})
        await self._emit(task_id, "dialing", {"phone": dial_phone})

        call_session = CallSession(task_id=task.id, start_time=datetime.now())
        await self.call_session_repository.create(call_session)
        logger.info("[task=%d] CallSession created", task.id)

        media_stream_ws_url = self._compute_ws_url()
        logger.info("[task=%d] Stream WS URL: %s", task.id, media_stream_ws_url)

        try:
            twiml = self._build_stream_twiml(task_id, user_id, language, media_stream_ws_url)
            logger.info("[task=%d] Initiating Twilio call with Media Stream TwiML", task.id)
            call_sid = await self._voice.initiate_call_with_twiml(
                to_phone=dial_phone,
                twiml=twiml,
                status_callback_url=f"{settings.BASE_URL}/webhooks/calls/{task_id}/status",
                recording_callback_url=f"{settings.BASE_URL}/webhooks/calls/{task_id}/recording",
            )
            logger.info("[task=%d] Twilio call initiated: call_sid=%s", task.id, call_sid)
        except Exception as call_error:
            logger.exception("[task=%d] Failed to initiate realtime call", task.id)
            task.status = TaskStatus.FAILED
            task.error_reason = str(call_error)
            await self.task_repository.update(task)
            await self._emit(
                task_id,
                "call_ended",
                {
                    "status": task.status,
                    "error_reason": task.error_reason,
                },
            )
            return task

        return task

    def _build_stream_twiml(
        self,
        task_id: int,
        user_id: int,
        language: str,
        media_stream_ws_url: str,
    ) -> str:
        """Build minimal TwiML. The system prompt is rebuilt server-side in the WS
        handler using task_id — keeps TwiML well under Twilio's 4000-char limit.
        """
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Connect>"
            f'<Stream url="{media_stream_ws_url}">'
            f'<Parameter name="task_id" value="{task_id}"/>'
            f'<Parameter name="user_id" value="{user_id}"/>'
            f'<Parameter name="language" value="{language}"/>'
            "</Stream>"
            "</Connect>"
            "</Response>"
        )

    def _compute_ws_url(self) -> str:
        base_url = settings.BASE_URL
        if base_url.startswith("https://"):
            return "wss://" + base_url[len("https://") :] + "/ws/media-stream"
        if base_url.startswith("http://"):
            return "ws://" + base_url[len("http://") :] + "/ws/media-stream"
        return base_url.rstrip("/") + "/ws/media-stream"

    def _resolve_phone(self, target_phone: str) -> str:
        if settings.TEST_PHONE_OVERRIDE:
            logger.info(
                "TEST_PHONE_OVERRIDE active: routing realtime call to %s instead of %s",
                settings.TEST_PHONE_OVERRIDE,
                target_phone,
            )
            return settings.TEST_PHONE_OVERRIDE
        return target_phone

    async def _emit(self, task_id: int, event: str, data: dict | None = None) -> None:
        if call_broadcaster.has_listeners(task_id):
            await call_broadcaster.emit(task_id, event, data)
