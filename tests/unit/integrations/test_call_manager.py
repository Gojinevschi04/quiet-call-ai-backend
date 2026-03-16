from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.calls.models import CallSession
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository
from app.modules.users.repository import UserRepository


def _make_manager(
    task_repo: MagicMock,
    template_repo: MagicMock,
    session_repo: MagicMock,
    log_repo: MagicMock,
    voice_mock: MagicMock | None = None,
    llm_mock: MagicMock | None = None,
) -> "CallManager":  # noqa: F821
    user_repo = MagicMock(spec=UserRepository)
    from app.integrations.call_manager import CallManager

    manager = CallManager(
        task_repository=task_repo,
        template_repository=template_repo,
        call_session_repository=session_repo,
        log_line_repository=log_repo,
        user_repository=user_repo,
    )
    manager._post_call = MagicMock()
    manager._post_call.process = AsyncMock()

    if voice_mock:
        manager._voice = voice_mock
    if llm_mock:
        manager._llm = llm_mock

    return manager


def _mock_voice() -> MagicMock:
    voice = MagicMock()
    voice.initiate_call = AsyncMock(return_value="CA123")
    voice.hangup = AsyncMock()
    voice.get_call_status = AsyncMock(return_value="in-progress")
    voice.get_recording_url = AsyncMock(return_value="https://example.com/rec.wav")
    voice.say_and_gather = AsyncMock(return_value="")
    return voice


def _mock_llm() -> MagicMock:
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value="Hello")
    llm.synthesize = AsyncMock(return_value=b"audio_bytes")
    llm.transcribe = AsyncMock(return_value="")
    llm.detect_intent = AsyncMock(return_value=None)
    return llm


def _mock_repos(
    task: Task, template: DialogTemplate
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    task_repo = MagicMock(spec=TaskRepository)
    task_repo.get_by_id = AsyncMock(return_value=task)
    task_repo.update = AsyncMock(return_value=task)

    template_repo = MagicMock(spec=TemplateRepository)
    template_repo.get_by_id = AsyncMock(return_value=template)

    session = CallSession(id=1, task_id=1, start_time=datetime.now())
    session_repo = MagicMock(spec=CallSessionRepository)
    session_repo.create = AsyncMock(return_value=session)
    session_repo.update = AsyncMock(return_value=session)

    log_repo = MagicMock(spec=LogLineRepository)
    log_repo.create_many = AsyncMock(return_value=[])

    return task_repo, template_repo, session_repo, log_repo


@pytest.mark.asyncio
async def test_execute_task_success(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Opening achieves objective on first message → completed."""
    task_repo, template_repo, session_repo, log_repo = _mock_repos(mock_task, mock_template)
    voice = _mock_voice()
    llm = _mock_llm()

    llm.generate_response = AsyncMock(
        side_effect=[
            "Hello, I'd like to make an appointment. [OBJECTIVE_ACHIEVED]",
            "Call summary: appointment confirmed.",
        ]
    )
    # say_and_gather returns empty (no response needed, objective already achieved)
    voice.say_and_gather = AsyncMock(return_value="")

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo, voice, llm)
    result = await manager.execute_task(1, user_id=1)

    assert result.status == TaskStatus.COMPLETED
    assert result.summary is not None
    voice.initiate_call.assert_called_once()
    voice.say_and_gather.assert_called()
    voice.hangup.assert_called_once()
    manager._post_call.process.assert_called_once()


@pytest.mark.asyncio
async def test_execute_task_multi_turn(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Multi-turn: AI speaks → human responds → AI replies → objective achieved."""
    task_repo, template_repo, session_repo, log_repo = _mock_repos(mock_task, mock_template)
    voice = _mock_voice()
    llm = _mock_llm()

    # say_and_gather: first call returns human speech, second returns empty
    voice.say_and_gather = AsyncMock(
        side_effect=["Yes, March 20 please.", ""]
    )
    llm.generate_response = AsyncMock(
        side_effect=[
            "Hello, I'd like to book an appointment.",
            "Great, March 20 works. [OBJECTIVE_ACHIEVED]",
            "Summary: appointment booked for March 20.",
        ]
    )
    llm.detect_intent = AsyncMock(return_value="confirmation")

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo, voice, llm)
    result = await manager.execute_task(1, user_id=1)

    assert result.status == TaskStatus.COMPLETED
    llm.detect_intent.assert_called_once_with("Yes, March 20 please.")
    assert voice.say_and_gather.call_count >= 2


@pytest.mark.asyncio
async def test_execute_task_rejection_intent(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Interlocutor rejects → AI says goodbye → task fails."""
    task_repo, template_repo, session_repo, log_repo = _mock_repos(mock_task, mock_template)
    voice = _mock_voice()
    llm = _mock_llm()

    voice.say_and_gather = AsyncMock(
        side_effect=["No, I'm not interested.", ""]
    )
    llm.generate_response = AsyncMock(
        side_effect=[
            "Hello, I'd like to book an appointment.",
            "Summary: Interlocutor rejected the appointment request.",
        ]
    )
    llm.detect_intent = AsyncMock(return_value="rejection")

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo, voice, llm)
    result = await manager.execute_task(1, user_id=1)

    assert result.status == TaskStatus.FAILED
    llm.detect_intent.assert_called_once()


@pytest.mark.asyncio
async def test_execute_task_noise_retry(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Empty speech triggers noise retries → max reached → call ends."""
    task_repo, template_repo, session_repo, log_repo = _mock_repos(mock_task, mock_template)
    voice = _mock_voice()
    llm = _mock_llm()

    # All say_and_gather calls return empty (silence)
    voice.say_and_gather = AsyncMock(return_value="")
    llm.generate_response = AsyncMock(
        side_effect=[
            "Hello, I'd like to book an appointment.",
            "Summary: Call ended due to no response.",
        ]
    )

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo, voice, llm)
    result = await manager.execute_task(1, user_id=1)

    assert result.status == TaskStatus.FAILED
    # Opening say_and_gather + apology retries
    assert voice.say_and_gather.call_count >= 3


@pytest.mark.asyncio
async def test_execute_task_call_failure(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Twilio call initiation fails → task marked FAILED."""
    task_repo, template_repo, session_repo, log_repo = _mock_repos(mock_task, mock_template)
    voice = _mock_voice()
    llm = _mock_llm()
    voice.initiate_call = AsyncMock(side_effect=Exception("Connection failed"))

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo, voice, llm)
    result = await manager.execute_task(1, user_id=1)

    assert result.status == TaskStatus.FAILED
    assert "Connection failed" in result.error_reason
    manager._post_call.process.assert_called_once()


@pytest.mark.asyncio
async def test_execute_task_not_found() -> None:
    task_repo = MagicMock(spec=TaskRepository)
    task_repo.get_by_id = AsyncMock(return_value=None)
    template_repo = MagicMock(spec=TemplateRepository)
    session_repo = MagicMock(spec=CallSessionRepository)
    log_repo = MagicMock(spec=LogLineRepository)

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo)
    with pytest.raises(ValueError, match="not found"):
        await manager.execute_task(999, user_id=1)


@pytest.mark.asyncio
async def test_execute_task_not_executable(mock_task: Task, mock_template: DialogTemplate) -> None:
    """Cannot execute a task that's already completed."""
    mock_task.status = TaskStatus.COMPLETED
    task_repo = MagicMock(spec=TaskRepository)
    task_repo.get_by_id = AsyncMock(return_value=mock_task)
    template_repo = MagicMock(spec=TemplateRepository)
    session_repo = MagicMock(spec=CallSessionRepository)
    log_repo = MagicMock(spec=LogLineRepository)

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo)
    with pytest.raises(ValueError, match="cannot be executed"):
        await manager.execute_task(1, user_id=1)


@pytest.mark.asyncio
async def test_build_system_prompt() -> None:
    task_repo = MagicMock(spec=TaskRepository)
    template_repo = MagicMock(spec=TemplateRepository)
    session_repo = MagicMock(spec=CallSessionRepository)
    log_repo = MagicMock(spec=LogLineRepository)

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo)

    prompt = manager._build_system_prompt(
        "Book an appointment",
        {"preferred_date": "March 20", "doctor_name": "Dr. Smith"},
    )

    assert "Book an appointment" in prompt
    assert "March 20" in prompt
    assert "Dr. Smith" in prompt
    assert "OBJECTIVE_ACHIEVED" in prompt
    assert "OBJECTIVE_FAILED" in prompt


@pytest.mark.asyncio
async def test_is_conversation_complete() -> None:
    task_repo = MagicMock(spec=TaskRepository)
    template_repo = MagicMock(spec=TemplateRepository)
    session_repo = MagicMock(spec=CallSessionRepository)
    log_repo = MagicMock(spec=LogLineRepository)

    manager = _make_manager(task_repo, template_repo, session_repo, log_repo)

    assert manager._is_conversation_complete("Great, confirmed! [OBJECTIVE_ACHIEVED]") is True
    assert manager._is_conversation_complete("Sorry, no availability. [OBJECTIVE_FAILED]") is True
    assert manager._is_conversation_complete("When would you prefer?") is False
