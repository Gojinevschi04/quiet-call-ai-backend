from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Brand colors
_PRIMARY = "#6366f1"
_SUCCESS = "#22c55e"
_DANGER = "#ef4444"
_WARNING = "#f59e0b"
_GRAY = "#6b7280"
_BG = "#f9fafb"
_CARD_BG = "#ffffff"


def _base_template(title: str, accent: str, content: str) -> str:
    """Wrap content in a branded email layout."""
    frontend_url = settings.CORS_ORIGINS.split(",")[0] if settings.CORS_ORIGINS else settings.BASE_URL
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"
    shadow = "box-shadow:0 1px 3px rgba(0,0,0,0.1)"
    card = f"background:{_CARD_BG};border-radius:16px;overflow:hidden;{shadow}"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:{_BG};font-family:{font};">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:40px 20px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="{card};">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,{_PRIMARY},{accent});padding:32px 40px;">
          <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">{title}</h1>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px 40px;">
          {content}
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:20px 40px 28px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;font-size:12px;color:{_GRAY};">
            <a href="{frontend_url}" style="color:{_PRIMARY};text-decoration:none;">Open Quiet Call AI</a>
            &nbsp;&middot;&nbsp; You received this email because you have an account with us.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _button(text: str, url: str, color: str = _PRIMARY) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:12px 28px;background:{color};'
        f'color:#fff;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;">'
        f"{text}</a>"
    )


def _info_box(label: str, value: str) -> str:
    return (
        f'<div style="background:#f3f4f6;padding:14px 18px;border-radius:10px;margin:8px 0;">'
        f'<span style="font-size:12px;color:{_GRAY};">{label}</span><br>'
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

    async def send_welcome(self, to_email: str) -> bool:
        frontend_url = settings.CORS_ORIGINS.split(",")[0] if settings.CORS_ORIGINS else settings.BASE_URL
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "Welcome to <strong>Quiet Call AI</strong>! Your account is ready.</p>"
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "You can now create tasks to automate your phone calls. "
            "Pick a template, fill in the details, and let the AI agent handle the conversation.</p>"
            f'<div style="text-align:center;margin:28px 0;">{_button("Go to Dashboard", frontend_url)}</div>'
        )
        return await self.send_email(
            to_email,
            "Welcome to Quiet Call AI",
            _base_template("Welcome aboard!", _PRIMARY, content),
        )

    async def send_password_reset(self, to_email: str, reset_token: str) -> bool:
        reset_url = f"{settings.BASE_URL}/auth/reset-password?token={reset_token}"
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "We received a request to reset your password. Click the button below to choose a new one.</p>"
            f'<div style="text-align:center;margin:28px 0;">{_button("Reset Password", reset_url, _WARNING)}</div>'
            '<p style="font-size:13px;color:#9ca3af;">If you did not request this, you can safely ignore this email. '
            "The link expires in 1 hour.</p>"
        )
        return await self.send_email(
            to_email,
            "Quiet Call AI — Reset Your Password",
            _base_template("Password Reset", _WARNING, content),
        )

    async def send_password_changed(self, to_email: str) -> bool:
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "Your password was changed successfully.</p>"
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "If you did not make this change, please reset your password immediately "
            "or contact support.</p>"
        )
        return await self.send_email(
            to_email,
            "Quiet Call AI — Password Changed",
            _base_template("Password Changed", _WARNING, content),
        )

    async def send_email_changed(self, to_old_email: str, new_email: str) -> bool:
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            f"Your account email has been changed to <strong>{new_email}</strong>.</p>"
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "If you did not make this change, please contact support immediately.</p>"
        )
        return await self.send_email(
            to_old_email,
            "Quiet Call AI — Email Address Changed",
            _base_template("Email Changed", _WARNING, content),
        )

    # ---- Task emails ----

    async def send_task_scheduled(self, to_email: str, task_phone: str, scheduled_time: str) -> bool:
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "Your call has been scheduled and will be executed automatically.</p>"
            + _info_box("Phone number", task_phone)
            + _info_box("Scheduled for", scheduled_time)
            + '<p style="font-size:13px;color:#9ca3af;margin-top:16px;">'
            "You will receive another email when the call is completed.</p>"
        )
        return await self.send_email(
            to_email,
            "Quiet Call AI — Call Scheduled",
            _base_template("Call Scheduled", _PRIMARY, content),
        )

    async def send_task_success(
        self, to_email: str, task_phone: str, summary: str, task_id: int | None = None
    ) -> bool:
        frontend_url = settings.CORS_ORIGINS.split(",")[0] if settings.CORS_ORIGINS else settings.BASE_URL
        details_btn = ""
        if task_id:
            details_btn = (
                f'<div style="text-align:center;margin:24px 0;">'
                f'{_button("View Full Transcript", f"{frontend_url}/tasks/{task_id}", _SUCCESS)}</div>'
            )
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "Your automated call has been completed successfully.</p>"
            + _info_box("Called", task_phone)
            + '<div style="background:#f0fdf4;padding:14px 18px;border-radius:10px;margin:12px 0;">'
            f'<span style="font-size:12px;color:{_SUCCESS};font-weight:600;">AI Summary</span><br>'
            f'<span style="font-size:14px;color:#374151;line-height:1.5;">{summary}</span></div>'
            + details_btn
        )
        return await self.send_email(
            to_email,
            "Quiet Call AI — Call Completed Successfully",
            _base_template("Call Completed", _SUCCESS, content),
        )

    async def send_task_failure(
        self, to_email: str, task_phone: str, error_reason: str, task_id: int | None = None
    ) -> bool:
        frontend_url = settings.CORS_ORIGINS.split(",")[0] if settings.CORS_ORIGINS else settings.BASE_URL
        retry_btn = ""
        if task_id:
            retry_btn = (
                f'<div style="text-align:center;margin:24px 0;">'
                f'{_button("View Task & Retry", f"{frontend_url}/tasks/{task_id}", _DANGER)}</div>'
            )
        content = (
            '<p style="font-size:15px;color:#374151;line-height:1.6;">'
            "Your automated call could not be completed.</p>"
            + _info_box("Called", task_phone)
            + '<div style="background:#fef2f2;padding:14px 18px;border-radius:10px;margin:12px 0;">'
            f'<span style="font-size:12px;color:{_DANGER};font-weight:600;">Reason</span><br>'
            f'<span style="font-size:14px;color:#991b1b;line-height:1.5;">{error_reason}</span></div>'
            + retry_btn
        )
        return await self.send_email(
            to_email,
            "Quiet Call AI — Call Failed",
            _base_template("Call Failed", _DANGER, content),
        )
