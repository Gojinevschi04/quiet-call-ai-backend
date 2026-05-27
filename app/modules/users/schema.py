import ipaddress
import re
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, field_validator

from app.core.constants import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")

WEBHOOK_ALLOWED_SCHEMES = {"https", "http"}
WEBHOOK_MAX_URL_LENGTH = 2048

ASSISTANT_NAME_MAX_LENGTH = 40
ASSISTANT_NAME_FORBIDDEN = set('<>{}\\"@\n\r\t')
ASSISTANT_NAME_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _validate_assistant_name(raw: str) -> str:
    """Short human-ish label (letters, spaces, dots, apostrophes, hyphens). Max 40 chars.

    Rejects newlines, control chars, template markers, angle brackets, @ to prevent
    prompt-injection payloads from flowing into OpenAI as the AI's identity.
    """
    if ASSISTANT_NAME_CONTROL.search(raw):
        raise ValueError("Assistant name cannot contain control characters")
    if any(char in ASSISTANT_NAME_FORBIDDEN for char in raw):
        raise ValueError("Assistant name contains forbidden characters")
    trimmed = raw.strip()
    if not trimmed:
        raise ValueError("Assistant name cannot be empty")
    if len(trimmed) > ASSISTANT_NAME_MAX_LENGTH:
        raise ValueError(f"Assistant name exceeds {ASSISTANT_NAME_MAX_LENGTH} characters")
    return trimmed


def _validate_webhook_url(url: str) -> str:
    """Reject webhook URLs that could be used for SSRF.

    Blocks: private/loopback/link-local IPs, non-http(s) schemes, overly long URLs.
    Hostnames resolve at call-time (the dispatcher should also check), but we do a
    structural check here so malformed entries never save.
    """
    if len(url) > WEBHOOK_MAX_URL_LENGTH:
        raise ValueError(f"Webhook URL exceeds {WEBHOOK_MAX_URL_LENGTH} characters")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in WEBHOOK_ALLOWED_SCHEMES:
        raise ValueError("Webhook URL must use http or https")
    if not parsed.hostname:
        raise ValueError("Webhook URL must have a hostname")
    host = parsed.hostname.lower()
    if host in ("localhost", "metadata.google.internal", "metadata"):
        raise ValueError("Webhook URL points to a blocked host")
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        return url
    if (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
    ):
        raise ValueError("Webhook URL points to a private/reserved IP")
    return url


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class UserInfo(BaseModel):
    id: int
    email: str | None
    role: UserRole


class UserCreate(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.USER
    password: str
    phone_number: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        if len(v) > PASSWORD_MAX_LENGTH:
            raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format")
        return v


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: UserRole | None = None
    phone_number: str | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format")
        return v


class UserResponse(BaseModel):
    id: int
    email: str | None
    role: UserRole
    phone_number: str | None = None
    email_notifications: bool = True
    webhook_url: str | None = None
    assistant_name: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    skip: int
    limit: int


class ProfileUpdate(BaseModel):
    phone_number: str | None = None
    email: EmailStr | None = None
    email_notifications: bool | None = None
    webhook_url: str | None = None
    assistant_name: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        return _validate_webhook_url(v)

    @field_validator("assistant_name")
    @classmethod
    def validate_assistant_name(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        return _validate_assistant_name(v)


class UserUsageResponse(BaseModel):
    """Aggregate token usage, call duration, and estimated cost for a user's calls."""

    call_count: int
    input_audio_tokens: int
    output_audio_tokens: int
    input_text_tokens: int
    output_text_tokens: int
    duration_seconds: int = 0
    twilio_cost_usd: float = 0.0
    openai_cost_usd: float = 0.0
    estimated_cost_usd: float


class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"New password must be at least {PASSWORD_MIN_LENGTH} characters")
        if len(v) > PASSWORD_MAX_LENGTH:
            raise ValueError(f"New password must be at most {PASSWORD_MAX_LENGTH} characters")
        return v
