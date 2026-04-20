import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator

from app.core.constants import MAX_SLOT_COUNT, MAX_SLOT_KEY_LENGTH, MAX_SLOT_VALUE_LENGTH


class TaskStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")

MIN_RATING = 1
MAX_RATING = 5
MAX_RATING_COMMENT_LENGTH = 1000

MIN_SLOT_VALUE_LENGTH = 2
MIN_UNIQUE_CHAR_RATIO = 0.4
LOW_ENTROPY_MIN_LENGTH = 4
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _validate_slot_value(key: str, value: str) -> None:
    """Reject slot values that look like garbage, control chars, or prompt-injection attempts."""
    if len(value) < MIN_SLOT_VALUE_LENGTH:
        raise ValueError(f"Slot value for '{key}' is too short (min {MIN_SLOT_VALUE_LENGTH} chars)")
    if CONTROL_CHAR_PATTERN.search(value) or "\n" in value or "\r" in value:
        raise ValueError(f"Slot value for '{key}' contains control characters or newlines")
    if "{{" in value or "}}" in value:
        raise ValueError(f"Slot value for '{key}' contains template markers")
    stripped = value.strip()
    if len(stripped) >= LOW_ENTROPY_MIN_LENGTH:
        unique_ratio = len(set(stripped.lower())) / len(stripped)
        if unique_ratio < MIN_UNIQUE_CHAR_RATIO:
            raise ValueError(
                f"Slot value for '{key}' looks like placeholder/garbage "
                f"(too few unique characters). Use a realistic value."
            )


class TaskBase(BaseModel):
    target_phone: str
    template_id: int
    slot_data: dict[str, str] = {}
    scheduled_time: datetime | None = None

    @field_validator("target_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format. Expected: +XXXXXXXXXXX")
        return v

    @field_validator("slot_data")
    @classmethod
    def validate_slot_data(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > MAX_SLOT_COUNT:
            raise ValueError(f"Maximum {MAX_SLOT_COUNT} slot values allowed")
        for key, value in v.items():
            if len(key) > MAX_SLOT_KEY_LENGTH:
                raise ValueError(f"Slot key '{key[:20]}...' exceeds {MAX_SLOT_KEY_LENGTH} characters")
            if len(value) > MAX_SLOT_VALUE_LENGTH:
                raise ValueError(f"Slot value for '{key}' exceeds {MAX_SLOT_VALUE_LENGTH} characters")
            _validate_slot_value(key, value)
        return v

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
        from app.core.config import settings
        if not (settings.CALL_WINDOW_START_HOUR <= v.hour < settings.CALL_WINDOW_END_HOUR):
            raise ValueError(
                f"Scheduled time must be within call hours "
                f"({settings.CALL_WINDOW_START_HOUR:02d}:00-{settings.CALL_WINDOW_END_HOUR:02d}:00)"
            )
        return v


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    """Internal update (used by system, not users)."""

    status: TaskStatus | None = None
    summary: str | None = None
    error_reason: str | None = None


class TaskEditRequest(BaseModel):
    """User-facing edit for pending/scheduled tasks."""

    target_phone: str | None = None
    slot_data: dict[str, str] | None = None
    scheduled_time: datetime | None = None

    @field_validator("target_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not PHONE_REGEX.match(v):
            raise ValueError("Invalid phone number format. Expected: +XXXXXXXXXXX")
        return v

    @field_validator("slot_data")
    @classmethod
    def validate_slot_data(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is not None:
            if len(v) > MAX_SLOT_COUNT:
                raise ValueError(f"Maximum {MAX_SLOT_COUNT} slot values allowed")
            for key, value in v.items():
                if len(key) > MAX_SLOT_KEY_LENGTH:
                    raise ValueError(f"Slot key '{key[:20]}...' exceeds {MAX_SLOT_KEY_LENGTH} characters")
                if len(value) > MAX_SLOT_VALUE_LENGTH:
                    raise ValueError(f"Slot value for '{key}' exceeds {MAX_SLOT_VALUE_LENGTH} characters")
                _validate_slot_value(key, value)
        return v

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
        from app.core.config import settings
        if not (settings.CALL_WINDOW_START_HOUR <= v.hour < settings.CALL_WINDOW_END_HOUR):
            raise ValueError(
                f"Scheduled time must be within call hours "
                f"({settings.CALL_WINDOW_START_HOUR:02d}:00-{settings.CALL_WINDOW_END_HOUR:02d}:00)"
            )
        return v


class TaskRatingRequest(BaseModel):
    """User feedback on a completed/failed call."""

    rating: int
    comment: str | None = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, rating: int) -> int:
        if not MIN_RATING <= rating <= MAX_RATING:
            raise ValueError(f"Rating must be an integer {MIN_RATING}-{MAX_RATING}")
        return rating

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, comment: str | None) -> str | None:
        if comment is not None and len(comment) > MAX_RATING_COMMENT_LENGTH:
            raise ValueError(f"Comment must be {MAX_RATING_COMMENT_LENGTH} characters or fewer")
        return comment


class TaskDuplicateRequest(BaseModel):
    """Duplicate an existing task into a new task for a different phone."""

    target_phone: str
    scheduled_time: datetime | None = None

    @field_validator("target_phone")
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        if not PHONE_REGEX.match(phone):
            raise ValueError("Invalid phone number format. Expected: +XXXXXXXXXXX")
        return phone

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, scheduled_time: datetime | None) -> datetime | None:
        if scheduled_time is None:
            return scheduled_time
        if scheduled_time <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
        from app.core.config import settings
        if not (settings.CALL_WINDOW_START_HOUR <= scheduled_time.hour < settings.CALL_WINDOW_END_HOUR):
            raise ValueError(
                f"Scheduled time must be within call hours "
                f"({settings.CALL_WINDOW_START_HOUR:02d}:00-{settings.CALL_WINDOW_END_HOUR:02d}:00)"
            )
        return scheduled_time


class TaskResponse(BaseModel):
    id: int
    target_phone: str
    status: TaskStatus
    template_id: int
    template_name: str | None = None
    user_id: int | None = None
    slot_data: dict[str, str]
    scheduled_time: datetime | None
    summary: str | None
    error_reason: str | None
    retry_count: int = 0
    next_retry_at: datetime | None = None
    user_rating: int | None = None
    user_rating_comment: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    limit: int
    offset: int


class TaskStatsResponse(BaseModel):
    total: int = 0
    pending: int = 0
    scheduled: int = 0
    in_progress: int = 0
    completed: int = 0
    failed: int = 0


class AdminStatsResponse(BaseModel):
    total_users: int = 0
    total_tasks: int = 0
    tasks_by_status: TaskStatsResponse = TaskStatsResponse()
    total_calls: int = 0
