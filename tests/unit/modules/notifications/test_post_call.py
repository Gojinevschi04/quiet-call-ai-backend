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
