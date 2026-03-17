from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger
from app.modules.notifications.constants import (
    BG,
    BOX_SHADOW,
    CARD_BG,
    DANGER,
    FONT_STACK,
    GRAY,
    PRIMARY,
    SUCCESS,
    WARNING,
)
from app.modules.notifications.translations import get_translations

logger = get_logger(__name__)


def _base_template(title: str, accent: str, content: str) -> str:
    """Wrap content in a branded email layout."""
    frontend_url = (
        settings.CORS_ORIGINS.split(",")[0]
        if settings.CORS_ORIGINS
        else settings.BASE_URL
    )
    card = f"background:{CARD_BG};border-radius:16px;overflow:hidden;{BOX_SHADOW}"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:{BG};font-family:{FONT_STACK};">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:40px 20px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="{card};">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,{PRIMARY},{accent});padding:32px 40px;">
          <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">{title}</h1>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px 40px;">
          {content}
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:20px 40px 28px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;font-size:12px;color:{GRAY};">
            <a href="{frontend_url}" style="color:{PRIMARY};text-decoration:none;">Open Quiet Call AI</a>
            &nbsp;&middot;&nbsp; You received this email because you have an account with us.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _button(text: str, url: str, color: str = PRIMARY) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:12px 28px;background:{color};'
        f'color:#fff;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;">'
        f"{text}</a>"
    )


def _info_box(label: str, value: str) -> str:
    return (
        f'<div style="background:#f3f4f6;padding:14px 18px;border-radius:10px;margin:8px 0;">'
        f'<span style="font-size:12px;color:{GRAY};">{label}</span><br>'
        f'<span style="font-size:15px;font-weight:600;color:#111827;">{value}</span></div>'
    )


class EmailService:
    async def send_email(self, to_email: str, subject: str, body_html: str) -> bool:
        if not settings.EMAIL_ENABLED:
            logger.info("Email disabled — would send to %s: %s", to_email, subject)
            return True

        message = EmailMessage()
        message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body_html, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True,
            )
            logger.info("Email sent to %s: %s", to_email, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
            return False

    # ---- Auth emails ----

    async def send_welcome(self, to_email: str, language: str = "en") -> bool:
        tr = get_translations(language)
        frontend_url = (
            settings.CORS_ORIGINS.split(",")[0]
            if settings.CORS_ORIGINS
            else settings.BASE_URL
        )
        content = (
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["welcome_body"]}</p>'
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["welcome_body2"]}</p>'
            f'<div style="text-align:center;margin:28px 0;">'
            f'{_button(tr["go_to_dashboard"], frontend_url)}</div>'
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["welcome_title"]}',
            _base_template(tr["welcome_title"], PRIMARY, content),
        )

    async def send_password_reset(
        self, to_email: str, reset_token: str, language: str = "en"
    ) -> bool:
        tr = get_translations(language)
        frontend_url = (
            settings.CORS_ORIGINS.split(",")[0]
            if settings.CORS_ORIGINS
            else settings.BASE_URL
        )
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"
        content = (
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["reset_body"]}</p>'
            f'<div style="text-align:center;margin:28px 0;">'
            f'{_button(tr["reset_button"], reset_url, WARNING)}</div>'
            f'<p style="font-size:13px;color:#9ca3af;">{tr["reset_note"]}</p>'
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["reset_title"]}',
            _base_template(tr["reset_title"], WARNING, content),
        )

    async def send_password_changed(self, to_email: str, language: str = "en") -> bool:
        tr = get_translations(language)
        content = (
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["password_changed_body"]}</p>'
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["password_changed_warning"]}</p>'
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["password_changed_title"]}',
            _base_template(tr["password_changed_title"], WARNING, content),
        )

    async def send_email_changed(
        self, to_old_email: str, new_email: str, language: str = "en"
    ) -> bool:
        tr = get_translations(language)
        content = (
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">'
            f'{tr["email_changed_body"]} <strong>{new_email}</strong>.</p>'
            f'<p style="font-size:15px;color:#374151;line-height:1.6;">{tr["email_changed_warning"]}</p>'
        )
        return await self.send_email(
            to_old_email,
            f'Quiet Call AI — {tr["email_changed_title"]}',
            _base_template(tr["email_changed_title"], WARNING, content),
        )

    # ---- Task emails ----

    async def send_task_scheduled(
        self, to_email: str, task_phone: str, scheduled_time: str, language: str = "en"
    ) -> bool:
        tr = get_translations(language)
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            f'{tr["scheduled_body"]}</p>'
            + _info_box(tr["phone_number"], task_phone)
            + _info_box(tr["scheduled_for"], scheduled_time)
            + '<p style="font-size:13px;color:#9ca3af;margin-top:16px;">'
            f'{tr["scheduled_followup"]}</p>'
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["call_scheduled"]}',
            _base_template(tr["call_scheduled"], PRIMARY, content),
        )

    async def send_task_success(
        self,
        to_email: str,
        task_phone: str,
        summary: str,
        task_id: int | None = None,
        language: str = "en",
    ) -> bool:
        tr = get_translations(language)
        frontend_url = (
            settings.CORS_ORIGINS.split(",")[0]
            if settings.CORS_ORIGINS
            else settings.BASE_URL
        )
        details_btn = ""
        if task_id:
            details_btn = (
                f'<div style="text-align:center;margin:24px 0;">'
                f'{_button(tr["view_transcript"], f"{frontend_url}/tasks/{task_id}", SUCCESS)}</div>'
            )
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            f'{tr["call_completed_body"]}</p>'
            + _info_box("Called", task_phone)
            + '<div style="background:#f0fdf4;padding:14px 18px;border-radius:10px;margin:12px 0;">'
            f'<span style="font-size:12px;color:{SUCCESS};font-weight:600;">{tr["ai_summary"]}</span><br>'
            f'<span style="font-size:14px;color:#374151;line-height:1.5;">{summary}</span></div>'
            + details_btn
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["call_completed"]}',
            _base_template(tr["call_completed"], SUCCESS, content),
        )

    async def send_task_failure(
        self,
        to_email: str,
        task_phone: str,
        error_reason: str,
        task_id: int | None = None,
        language: str = "en",
    ) -> bool:
        tr = get_translations(language)
        frontend_url = (
            settings.CORS_ORIGINS.split(",")[0]
            if settings.CORS_ORIGINS
            else settings.BASE_URL
        )
        retry_btn = ""
        if task_id:
            retry_btn = (
                f'<div style="text-align:center;margin:24px 0;">'
                f'{_button(tr["view_task_retry"], f"{frontend_url}/tasks/{task_id}", DANGER)}</div>'
            )
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            f'{tr["call_failed_body"]}</p>'
            + _info_box("Called", task_phone)
            + '<div style="background:#fef2f2;padding:14px 18px;border-radius:10px;margin:12px 0;">'
            f'<span style="font-size:12px;color:{DANGER};font-weight:600;">{tr["reason"]}</span><br>'
            f'<span style="font-size:14px;color:#991b1b;line-height:1.5;">{error_reason}</span></div>'
            + retry_btn
        )
        return await self.send_email(
            to_email,
            f'Quiet Call AI — {tr["call_failed"]}',
            _base_template(tr["call_failed"], DANGER, content),
        )

    # ---- Feedback ----

    async def send_feedback(
        self, sender_name: str, sender_email: str, message: str
    ) -> bool:
        recipients = [
            e.strip() for e in settings.FEEDBACK_EMAILS.split(",") if e.strip()
        ]
        if not recipients:
            logger.warning("No FEEDBACK_EMAILS configured, skipping feedback delivery")
            return False

        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "New feedback received from the contact form.</p>"
            + _info_box("From", f"{sender_name} ({sender_email})")
            + '<div style="background:#f3f4f6;padding:14px 18px;border-radius:10px;margin:12px 0;">'
            f'<span style="font-size:12px;color:{GRAY};font-weight:600;">Message</span><br>'
            f'<span style="font-size:14px;color:#374151;line-height:1.6;white-space:pre-wrap;">'
            f"{message}</span></div>"
            + f'<p style="font-size:13px;color:#9ca3af;">Reply directly to '
            f'<a href="mailto:{sender_email}" style="color:{PRIMARY};">{sender_email}</a></p>'
        )
        subject = f"Quiet Call AI — Feedback from {sender_name}"
        body = _base_template("New Feedback", PRIMARY, content)

        success = True
        for recipient in recipients:
            result = await self.send_email(recipient, subject, body)
            if not result:
                success = False
        return success
