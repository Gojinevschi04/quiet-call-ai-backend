import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, field_validator


class TaskStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


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
        if len(v) > 20:
            raise ValueError("Maximum 20 slot values allowed")
        for key, value in v.items():
            if len(key) > 50:
                raise ValueError(f"Slot key '{key[:20]}...' exceeds 50 characters")
            if len(value) > 500:
                raise ValueError(f"Slot value for '{key}' exceeds 500 characters")
        return v

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, v: datetime | None) -> datetime | None:
        if v is not None and v <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
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
            if len(v) > 20:
                raise ValueError("Maximum 20 slot values allowed")
            for key, value in v.items():
                if len(key) > 50:
                    raise ValueError(f"Slot key '{key[:20]}...' exceeds 50 characters")
                if len(value) > 500:
                    raise ValueError(f"Slot value for '{key}' exceeds 500 characters")
        return v


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
