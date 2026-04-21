from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.calls.models import CallSession
from app.modules.calls.repository import CallSessionRepository, LogLineRepository
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schema import TaskStatus
from app.modules.templates.models import DialogTemplate
from app.modules.templates.repository import TemplateRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserRole


@pytest.mark.asyncio
async def test_process_completed_task(mock_task: Task, mock_call_session: CallSession) -> None:
    mock_task.status = TaskStatus.COMPLETED
    mock_task.summary = "Appointment booked for March 20."

    mock_user = User(id=1, email="user@example.com", role=UserRole.USER)

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_session_repo = MagicMock(spec=CallSessionRepository)
    mock_session_repo.get_by_task_id = AsyncMock(return_value=mock_call_session)
    mock_log_repo = MagicMock(spec=LogLineRepository)
    mock_log_repo.get_by_session_id = AsyncMock(return_value=[])
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template = MagicMock(spec=DialogTemplate)
    mock_template.language = "en"
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    with patch("app.modules.notifications.post_call.EmailService") as mock_email_cls:
        mock_email = MagicMock()
        mock_email.send_task_success = AsyncMock(return_value=True)
        mock_email.send_task_failure = AsyncMock(return_value=True)
        mock_email_cls.return_value = mock_email

        from app.modules.notifications.post_call import PostCallProcessor

        processor = PostCallProcessor(
            task_repository=mock_task_repo,
            user_repository=mock_user_repo,
            call_session_repository=mock_session_repo,
            log_line_repository=mock_log_repo,
            template_repository=mock_template_repo,
        )
        await processor.process(mock_task)

        mock_email.send_task_success.assert_called_once_with(
            to_email="user@example.com",
            task_phone=mock_task.target_phone,
            summary="Appointment booked for March 20.",
            task_id=mock_task.id,
            language="en",
        )
        mock_email.send_task_failure.assert_not_called()


@pytest.mark.asyncio
async def test_process_failed_task(mock_task: Task) -> None:
    mock_task.status = TaskStatus.FAILED
    mock_task.error_reason = "No answer after 3 retries"

    mock_user = User(id=1, email="user@example.com", role=UserRole.USER)

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_session_repo = MagicMock(spec=CallSessionRepository)
    mock_session_repo.get_by_task_id = AsyncMock(return_value=None)
    mock_log_repo = MagicMock(spec=LogLineRepository)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template = MagicMock(spec=DialogTemplate)
    mock_template.language = "en"
    mock_template_repo.get_by_id = AsyncMock(return_value=mock_template)

    with patch("app.modules.notifications.post_call.EmailService") as mock_email_cls:
        mock_email = MagicMock()
        mock_email.send_task_success = AsyncMock(return_value=True)
        mock_email.send_task_failure = AsyncMock(return_value=True)
        mock_email_cls.return_value = mock_email

        from app.modules.notifications.post_call import PostCallProcessor

        processor = PostCallProcessor(
            task_repository=mock_task_repo,
            user_repository=mock_user_repo,
            call_session_repository=mock_session_repo,
            log_line_repository=mock_log_repo,
            template_repository=mock_template_repo,
        )
        await processor.process(mock_task)

        mock_email.send_task_failure.assert_called_once_with(
            to_email="user@example.com",
            task_phone=mock_task.target_phone,
            error_reason="No answer after 3 retries",
            task_id=mock_task.id,
            language="en",
        )
        mock_email.send_task_success.assert_not_called()


@pytest.mark.asyncio
async def test_process_no_user_email(mock_task: Task) -> None:
    mock_task.status = TaskStatus.COMPLETED

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=None)
    mock_session_repo = MagicMock(spec=CallSessionRepository)
    mock_log_repo = MagicMock(spec=LogLineRepository)
    mock_template_repo = MagicMock(spec=TemplateRepository)

    with patch("app.modules.notifications.post_call.EmailService") as mock_email_cls:
        mock_email = MagicMock()
        mock_email.send_task_success = AsyncMock()
        mock_email.send_task_failure = AsyncMock()
        mock_email_cls.return_value = mock_email

        from app.modules.notifications.post_call import PostCallProcessor

        processor = PostCallProcessor(
            task_repository=mock_task_repo,
            user_repository=mock_user_repo,
            call_session_repository=mock_session_repo,
            log_line_repository=mock_log_repo,
            template_repository=mock_template_repo,
        )
        await processor.process(mock_task)

        mock_email.send_task_success.assert_not_called()
        mock_email.send_task_failure.assert_not_called()


@pytest.mark.asyncio
async def test_process_continues_webhook_when_email_raises(mock_task: Task) -> None:
    """Regression: if email raises, webhook + archive still complete (gather w/ return_exceptions)."""
    from app.modules.notifications.post_call import PostCallProcessor

    mock_task.status = TaskStatus.COMPLETED
    user = User(
        id=1,
        email="user@example.com",
        role=UserRole.USER,
        email_notifications=True,
        webhook_url="https://hooks.example.com/x",
    )

    mock_task_repo = MagicMock(spec=TaskRepository)
    mock_task_repo.update = AsyncMock(return_value=mock_task)
    mock_user_repo = MagicMock(spec=UserRepository)
    mock_user_repo.get_by_id = AsyncMock(return_value=user)
    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_by_task_id = AsyncMock(return_value=None)
    mock_log_line_repo = MagicMock(spec=LogLineRepository)
    mock_template_repo = MagicMock(spec=TemplateRepository)
    mock_template_repo.get_by_id = AsyncMock(return_value=None)

    processor = PostCallProcessor(
        task_repository=mock_task_repo,
        user_repository=mock_user_repo,
        call_session_repository=mock_call_session_repo,
        log_line_repository=mock_log_line_repo,
        template_repository=mock_template_repo,
    )

    webhook_mock = AsyncMock()
    with (
        patch(
            "app.modules.notifications.post_call.PostCallProcessor._send_notification",
            new=AsyncMock(side_effect=RuntimeError("SMTP down")),
        ),
        patch(
            "app.modules.notifications.webhook_dispatcher.send_task_webhook",
            new=webhook_mock,
        ),
    ):
        await processor.process(mock_task)

    webhook_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_logs_skips_when_no_call_session(mock_task: Task) -> None:
    """_archive_logs: no call session → no log-line query, no crash."""
    from app.modules.notifications.post_call import PostCallProcessor

    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_by_task_id = AsyncMock(return_value=None)
    mock_log_line_repo = MagicMock(spec=LogLineRepository)
    mock_log_line_repo.get_by_session_id = AsyncMock()

    processor = PostCallProcessor(
        task_repository=MagicMock(spec=TaskRepository),
        user_repository=MagicMock(spec=UserRepository),
        call_session_repository=mock_call_session_repo,
        log_line_repository=mock_log_line_repo,
        template_repository=MagicMock(spec=TemplateRepository),
    )
    await processor._archive_logs(mock_task)

    mock_log_line_repo.get_by_session_id.assert_not_called()


@pytest.mark.asyncio
async def test_archive_logs_fetches_log_lines_when_session_exists(
    mock_task: Task, mock_call_session: CallSession,
) -> None:
    """_archive_logs: with a call session, log lines are fetched for archival."""
    from app.modules.notifications.post_call import PostCallProcessor

    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_by_task_id = AsyncMock(return_value=mock_call_session)
    mock_log_line_repo = MagicMock(spec=LogLineRepository)
    mock_log_line_repo.get_by_session_id = AsyncMock(return_value=[])

    processor = PostCallProcessor(
        task_repository=MagicMock(spec=TaskRepository),
        user_repository=MagicMock(spec=UserRepository),
        call_session_repository=mock_call_session_repo,
        log_line_repository=mock_log_line_repo,
        template_repository=MagicMock(spec=TemplateRepository),
    )
    await processor._archive_logs(mock_task)

    mock_log_line_repo.get_by_session_id.assert_awaited_once_with(mock_call_session.id)


@pytest.mark.asyncio
async def test_save_recording_locally_skips_when_no_recording_uri(mock_task: Task) -> None:
    """_save_recording_locally: no recording URI → early return, no download."""
    from app.modules.notifications.post_call import PostCallProcessor

    call_session_without_recording = MagicMock()
    call_session_without_recording.recording_uri = None
    call_session_without_recording.local_recording_path = None

    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_by_task_id = AsyncMock(return_value=call_session_without_recording)

    processor = PostCallProcessor(
        task_repository=MagicMock(spec=TaskRepository),
        user_repository=MagicMock(spec=UserRepository),
        call_session_repository=mock_call_session_repo,
        log_line_repository=MagicMock(spec=LogLineRepository),
        template_repository=MagicMock(spec=TemplateRepository),
    )

    with patch("app.integrations.twilio_adapter.TwilioAdapter") as mock_adapter_cls:
        await processor._save_recording_locally(mock_task)

    mock_adapter_cls.assert_not_called()


@pytest.mark.asyncio
async def test_save_recording_locally_skips_when_already_saved(mock_task: Task) -> None:
    """_save_recording_locally: if local_recording_path is set, skip re-download."""
    from app.modules.notifications.post_call import PostCallProcessor

    already_saved = MagicMock()
    already_saved.recording_uri = "https://api.twilio.com/rec.wav"
    already_saved.local_recording_path = "/tmp/recordings/task_1.mp3"

    mock_call_session_repo = MagicMock(spec=CallSessionRepository)
    mock_call_session_repo.get_by_task_id = AsyncMock(return_value=already_saved)

    processor = PostCallProcessor(
        task_repository=MagicMock(spec=TaskRepository),
        user_repository=MagicMock(spec=UserRepository),
        call_session_repository=mock_call_session_repo,
        log_line_repository=MagicMock(spec=LogLineRepository),
        template_repository=MagicMock(spec=TemplateRepository),
    )

    with patch("app.integrations.twilio_adapter.TwilioAdapter") as mock_adapter_cls:
        await processor._save_recording_locally(mock_task)

    mock_adapter_cls.assert_not_called()
