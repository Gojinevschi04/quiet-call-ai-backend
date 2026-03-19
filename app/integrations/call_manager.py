from datetime import datetime
from typing import Annotated

from fastapi import Depends

from app.core.constants import CALL_ANSWER_TIMEOUT_SECONDS
from app.core.logging import get_logger
from app.core.ws_manager import call_broadcaster
from app.integrations.conversation import ConversationManager
from app.integrations.interfaces import ILLMProvider
from app.integrations.openai_adapter import OpenAIAdapter
from app.integrations.prompt_builder import PromptBuilder
from app.integrations.twilio_adapter import TwilioAdapter
from app.modules.calls.models import CallSession
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.notifications.post_call import PostCallProcessor
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.repository import TemplateRepository
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

MAX_DIALOG_TURNS = 10
MAX_RETRY_ON_NOISE = 3
INTENT_REJECTION = "rejection"
NOISE_APOLOGY = "I'm sorry, I didn't catch that. Could you please repeat?"
REJECTION_FAREWELL = "I understand. Thank you for your time. Goodbye. [OBJECTIVE_FAILED]"


class CallManager:
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
        self._voice: TwilioAdapter = TwilioAdapter()
        self._llm: ILLMProvider = OpenAIAdapter()
        self._post_call = PostCallProcessor(
            task_repository=task_repository,
            user_repository=user_repository,
            call_session_repository=call_session_repository,
            log_line_repository=log_line_repository,
            template_repository=template_repository,
        )

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

        task.status = TaskStatus.IN_PROGRESS
        await self.task_repository.update(task)
        logger.info("Executing task %d: calling %s", task.id, task.target_phone)

        await self._emit(task_id, "status_change", {"status": TaskStatus.IN_PROGRESS})

        call_session = CallSession(task_id=task.id, start_time=datetime.now())
        call_session = await self.call_session_repository.create(call_session)
        callback_url = f"{self._get_callback_base()}/webhooks/calls/{task.id}"
        conv = ConversationManager(MAX_DIALOG_TURNS, MAX_RETRY_ON_NOISE)

        try:
            lang = template.language or "en"
            system_prompt = self._build_system_prompt(template.base_script, task.slot_data, lang)

            await self._emit(task_id, "dialing", {"phone": task.target_phone})

            call_sid = await self._voice.initiate_call(
                to_phone=task.target_phone,
                callback_url=callback_url,
            )
            logger.info("Call SID: %s for task %d (language: %s)", call_sid, task.id, lang)
            await self._wait_for_answer(call_sid)

            await self._emit(task_id, "call_answered")

            opening = await self._llm.generate_response(conv.history, system_prompt)
            conv.add_agent_message(opening, call_session.id)
            await self._emit(task_id, "message", {"speaker": "agent", "text": opening})

            interlocutor_text = await self._voice.say_and_gather(call_sid, opening, callback_url, lang)

            await self._run_dialog_loop(
                task_id, call_sid, conv, call_session, system_prompt, callback_url, lang, interlocutor_text
            )

            await self._voice.hangup(call_sid)
            call_session.duration = int((datetime.now() - call_session.start_time).total_seconds())
            call_session.recording_uri = await self._voice.get_recording_url(call_sid)
            await self.call_session_repository.update(call_session)

            await self._emit(task_id, "generating_summary")

            summary = await self._generate_summary(conv, lang)
            task.status = TaskStatus.COMPLETED if conv.has_objective_achieved() else TaskStatus.FAILED
            task.summary = summary
            if not conv.has_objective_achieved():
                task.error_reason = "Objective not achieved during conversation"

        except Exception as e:
            logger.error("Task %d failed: %s", task.id, str(e))
            task.status = TaskStatus.FAILED
            task.error_reason = str(e)

        await self.task_repository.update(task)

        if conv.log_lines:
            await self.log_line_repository.create_many(conv.log_lines)

        logger.info("Task %d finished with status: %s", task.id, task.status)

        await self._emit(task_id, "call_ended", {
            "status": task.status,
            "summary": task.summary,
            "error_reason": task.error_reason,
        })

        await self._post_call.process(task)
        return task

    async def _run_dialog_loop(
        self,
        task_id: int,
        call_sid: str,
        conv: ConversationManager,
        call_session: CallSession,
        system_prompt: str,
        callback_url: str,
        lang: str,
        interlocutor_text: str,
    ) -> None:
        for _turn in range(conv.max_turns):
            if not interlocutor_text.strip():
                conv.noise_retries += 1
                if conv.noise_retries >= conv.max_noise_retries:
                    conv.add_agent_message("[Max noise retries reached]", call_session.id)
                    break
                conv.add_agent_message(NOISE_APOLOGY, call_session.id)
                await self._emit(task_id, "message", {"speaker": "agent", "text": NOISE_APOLOGY})
                interlocutor_text = await self._voice.say_and_gather(
                    call_sid, NOISE_APOLOGY, callback_url, lang
                )
                continue

            conv.noise_retries = 0
            detected_intent = await self._llm.detect_intent(interlocutor_text)
            conv.add_interlocutor_message(interlocutor_text, detected_intent, call_session.id)
            await self._emit(task_id, "message", {
                "speaker": "interlocutor",
                "text": interlocutor_text,
                "intent": detected_intent,
            })

            if detected_intent == INTENT_REJECTION:
                conv.add_agent_message(REJECTION_FAREWELL, call_session.id)
                await self._emit(task_id, "message", {"speaker": "agent", "text": REJECTION_FAREWELL})
                await self._voice.say_and_gather(call_sid, REJECTION_FAREWELL, callback_url, lang)
                break

            agent_reply = await self._llm.generate_response(conv.history, system_prompt)
            conv.add_agent_message(agent_reply, call_session.id)
            await self._emit(task_id, "message", {"speaker": "agent", "text": agent_reply})

            if conv.is_complete(agent_reply):
                await self._voice.say_and_gather(call_sid, agent_reply, callback_url, lang)
                break

            interlocutor_text = await self._voice.say_and_gather(call_sid, agent_reply, callback_url, lang)

    async def _wait_for_answer(self, call_sid: str, max_wait: int = CALL_ANSWER_TIMEOUT_SECONDS) -> None:
        """Poll call status until it's answered or fails."""
        import asyncio

        from app.core.constants import CALL_STATUS_POLL_INTERVAL_SECONDS

        for _ in range(max_wait):
            status = await self._voice.get_call_status(call_sid)
            if status == "in-progress":
                logger.info("Call %s answered", call_sid)
                return
            if status in ("completed", "busy", "no-answer", "canceled", "failed"):
                raise RuntimeError(f"Call ended before being answered (status: {status})")
            await asyncio.sleep(CALL_STATUS_POLL_INTERVAL_SECONDS)

        raise RuntimeError("Call was not answered within timeout")

    def _build_system_prompt(self, base_script: str, slot_data: dict[str, str], language: str = "en") -> str:
        return PromptBuilder.build_system_prompt(base_script, slot_data, language)

    async def _generate_summary(self, conv: ConversationManager, language: str = "en") -> str:
        return await self._llm.generate_response(
            [{"role": "user", "content": f"Conversation:\n{conv.format_history()}"}],
            PromptBuilder.build_summary_prompt(language),
        )

    def _get_callback_base(self) -> str:
        from app.core.config import settings

        return settings.BASE_URL

    async def _emit(self, task_id: int, event: str, data: dict | None = None) -> None:
        """Emit event to WebSocket clients if any are listening."""
        if call_broadcaster.has_listeners(task_id):
            await call_broadcaster.emit(task_id, event, data)
