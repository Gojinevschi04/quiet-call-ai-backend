import asyncio
from typing import Annotated

import aiofiles
from fastapi import Depends

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.notifications.email_service import EmailService
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.repository import TemplateRepository
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

RECORDINGS_DIR = settings.STORAGE_DIR / "recordings"


class PostCallProcessor:
    def __init__(
        self,
        task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
        call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
        log_line_repository: Annotated[LogLineRepository, Depends(LogLineRepository)],
        template_repository: Annotated[TemplateRepository, Depends(TemplateRepository)],
    ) -> None:
        self.task_repository = task_repository
        self.user_repository = user_repository
        self.call_session_repository = call_session_repository
        self.log_line_repository = log_line_repository
        self.template_repository = template_repository
        self.email_service = EmailService()

    async def process(self, task: Task) -> None:
        logger.info("Post-call processing for task %d (status: %s)", task.id, task.status)

        user = await self.user_repository.get_by_id(task.user_id)
        if not user or not user.email:
            logger.warning("No user/email found for task %d, skipping notification", task.id)
            return

        coroutines = [
            self._archive_logs(task),
            self._save_recording_locally(task),
        ]
        if user.email_notifications:
            coroutines.append(self._send_notification(task, user.email))
        else:
            logger.info("Email notifications disabled for user %d, skipping for task %d", user.id, task.id)

        if user.webhook_url:
            from app.modules.notifications.webhook_dispatcher import send_task_webhook
            coroutines.append(send_task_webhook(user.webhook_url, task))

        await asyncio.gather(*coroutines)

        logger.info("Post-call processing completed for task %d", task.id)

    async def _send_notification(self, task: Task, user_email: str) -> None:
        template = await self.template_repository.get_by_id(task.template_id)
        language = template.language if template else "en"

        if task.status == TaskStatus.COMPLETED:
            await self.email_service.send_task_success(
                to_email=user_email,
                task_phone=task.target_phone,
                summary=task.summary or "Call completed successfully.",
                task_id=task.id,
                language=language,
            )
        elif task.status == TaskStatus.FAILED:
            await self.email_service.send_task_failure(
                to_email=user_email,
                task_phone=task.target_phone,
                error_reason=task.error_reason or "Unknown error.",
                task_id=task.id,
                language=language,
            )

    async def _archive_logs(self, task: Task) -> None:
        call_session = await self.call_session_repository.get_by_task_id(task.id)
        if not call_session:
            logger.debug("No call session to archive for task %d", task.id)
            return

        log_lines = await self.log_line_repository.get_by_session_id(call_session.id)
        logger.info(
            "Archived %d log lines for task %d (session %d, duration %ss)",
            len(log_lines),
            task.id,
            call_session.id,
            call_session.duration or "N/A",
        )

    async def _save_recording_locally(self, task: Task) -> None:
        call_session = await self.call_session_repository.get_by_task_id(task.id)
        if not call_session or not call_session.recording_uri:
            return

        if call_session.local_recording_path:
            logger.debug("Recording already saved locally for task %d", task.id)
            return

        try:
            from app.integrations.twilio_adapter import TwilioAdapter

            adapter = TwilioAdapter()
            recording_url = call_session.recording_uri.replace(".wav", ".mp3")
            audio_bytes = await adapter.get_recording_audio(recording_url)

            RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"task_{task.id}.mp3"
            file_path = RECORDINGS_DIR / filename

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(audio_bytes)

            call_session.local_recording_path = str(file_path)
            await self.call_session_repository.update(call_session)

            logger.info("Saved recording locally for task %d (%d bytes)", task.id, len(audio_bytes))
        except Exception:
            logger.warning("Failed to save recording locally for task %d", task.id, exc_info=True)
