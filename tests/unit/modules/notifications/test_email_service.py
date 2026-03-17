from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def _mock_settings() -> None:
    """Patch settings for all email tests — EMAIL_ENABLED=False so no real SMTP."""
    with patch("app.modules.notifications.email_service.settings") as mock_settings:
        mock_settings.EMAIL_ENABLED = False
        mock_settings.BASE_URL = "http://localhost:8000"
        mock_settings.CORS_ORIGINS = "http://localhost:3000"
        yield mock_settings


# ---- send_email (core transport) ----


@pytest.mark.asyncio
async def test_send_email_disabled() -> None:
    with patch("app.modules.notifications.email_service.settings") as mock_settings:
        mock_settings.EMAIL_ENABLED = False

        from app.modules.notifications.email_service import EmailService

        service = EmailService()
        result = await service.send_email("user@example.com", "Test", "<p>Hello</p>")

        assert result is True


@pytest.mark.asyncio
async def test_send_email_enabled_success() -> None:
    with (
        patch("app.modules.notifications.email_service.settings") as mock_settings,
        patch("app.modules.notifications.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.EMAIL_ENABLED = True
        mock_settings.EMAIL_FROM = "noreply@test.com"
        mock_settings.EMAIL_FROM_NAME = "Test"
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"

        from app.modules.notifications.email_service import EmailService

        service = EmailService()
        result = await service.send_email("user@example.com", "Test", "<p>Hello</p>")

        assert result is True
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_failure() -> None:
    with (
        patch("app.modules.notifications.email_service.settings") as mock_settings,
        patch("app.modules.notifications.email_service.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.EMAIL_ENABLED = True
        mock_settings.EMAIL_FROM = "noreply@test.com"
        mock_settings.EMAIL_FROM_NAME = "Test"
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_send.side_effect = Exception("SMTP connection failed")

        from app.modules.notifications.email_service import EmailService

        service = EmailService()
        result = await service.send_email("user@example.com", "Test", "<p>Hello</p>")

        assert result is False


# ---- Auth emails ----


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_welcome() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_welcome("new@example.com")

    assert result is True
    service.send_email.assert_called_once()
    to_email, subject, body_html = service.send_email.call_args[0]
    assert to_email == "new@example.com"
    assert "Welcome" in subject
    assert "Welcome" in body_html
    assert "Go to Dashboard" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_password_reset() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_password_reset("user@example.com", "test-reset-token-123")

    assert result is True
    service.send_email.assert_called_once()
    to_email, subject, body_html = service.send_email.call_args[0]
    assert to_email == "user@example.com"
    assert "Reset" in subject
    assert "test-reset-token-123" in body_html
    assert "1 hour" in body_html
    # Reset link should point to frontend, not backend
    assert "localhost:3000/reset-password" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_password_changed() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_password_changed("user@example.com")

    assert result is True
    service.send_email.assert_called_once()
    to_email, subject, body_html = service.send_email.call_args[0]
    assert to_email == "user@example.com"
    assert "Changed" in subject
    assert "changed successfully" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_email_changed() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_email_changed("old@example.com", "new@example.com")

    assert result is True
    service.send_email.assert_called_once()
    to_email, subject, body_html = service.send_email.call_args[0]
    assert to_email == "old@example.com"
    assert "new@example.com" in body_html
    assert "Changed" in subject


# ---- Task emails ----


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_scheduled() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_task_scheduled("user@example.com", "+37312345678", "2026-03-20 10:00")

    assert result is True
    service.send_email.assert_called_once()
    to_email, subject, body_html = service.send_email.call_args[0]
    assert to_email == "user@example.com"
    assert "Scheduled" in subject
    assert "+37312345678" in body_html
    assert "2026-03-20 10:00" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_success_email() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_task_success(
        to_email="user@example.com",
        task_phone="+37312345678",
        summary="Appointment confirmed for March 20.",
    )

    assert result is True
    service.send_email.assert_called_once()
    _to, subject, body_html = service.send_email.call_args[0]
    assert "Completed" in subject
    assert "Appointment confirmed" in body_html
    assert "+37312345678" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_success_with_task_id() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    await service.send_task_success(
        to_email="user@example.com",
        task_phone="+37312345678",
        summary="Done.",
        task_id=42,
    )

    _to, _subj, body_html = service.send_email.call_args[0]
    assert "View Full Transcript" in body_html
    assert "/tasks/42" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_success_without_task_id() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    await service.send_task_success(
        to_email="user@example.com",
        task_phone="+37312345678",
        summary="Done.",
    )

    _to, _subj, body_html = service.send_email.call_args[0]
    assert "View Full Transcript" not in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_failure_email() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    result = await service.send_task_failure(
        to_email="user@example.com",
        task_phone="+37312345678",
        error_reason="No answer after 3 retries.",
    )

    assert result is True
    service.send_email.assert_called_once()
    _to, subject, body_html = service.send_email.call_args[0]
    assert "Failed" in subject
    assert "No answer after 3 retries" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_failure_with_task_id() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    await service.send_task_failure(
        to_email="user@example.com",
        task_phone="+37312345678",
        error_reason="Failed.",
        task_id=7,
    )

    _to, _subj, body_html = service.send_email.call_args[0]
    assert "View Task" in body_html
    assert "/tasks/7" in body_html


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_send_task_failure_without_task_id() -> None:
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    await service.send_task_failure(
        to_email="user@example.com",
        task_phone="+37312345678",
        error_reason="Failed.",
    )

    _to, _subj, body_html = service.send_email.call_args[0]
    assert "View Task" not in body_html


# ---- Template rendering ----


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_settings")
async def test_all_emails_use_branded_template() -> None:
    """Every email method should produce HTML with the base template structure."""
    from app.modules.notifications.email_service import EmailService

    service = EmailService()
    service.send_email = AsyncMock(return_value=True)

    await service.send_welcome("u@test.com")
    await service.send_password_reset("u@test.com", "tok")
    await service.send_password_changed("u@test.com")
    await service.send_email_changed("u@test.com", "n@test.com")
    await service.send_task_scheduled("u@test.com", "+123", "2026-01-01")
    await service.send_task_success(to_email="u@test.com", task_phone="+123", summary="ok")
    await service.send_task_failure(to_email="u@test.com", task_phone="+123", error_reason="err")

    assert service.send_email.call_count == 7
    for call in service.send_email.call_args_list:
        _to, _subj, body_html = call[0]
        assert "<!DOCTYPE html>" in body_html
        assert "Quiet Call AI" in body_html
        assert "Open Quiet Call AI" in body_html
