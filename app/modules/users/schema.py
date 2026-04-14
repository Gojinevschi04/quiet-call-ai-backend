import re
from enum import StrEnum

from pydantic import BaseModel, EmailStr, field_validator

from app.core.constants import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


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
