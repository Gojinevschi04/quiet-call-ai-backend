from datetime import datetime

from sqlmodel import Field

from app.core.models import BaseModel
from app.modules.users.schema import UserRole


class User(BaseModel, table=True):
    email: str | None = Field(index=True, nullable=True)
    role: UserRole = Field(default=UserRole.USER)
    hashed_password: str | None = Field(nullable=True)
    phone_number: str | None = Field(default=None, nullable=True)
    email_notifications: bool = Field(default=True, nullable=False)
    webhook_url: str | None = Field(default=None, nullable=True)
    password_changed_at: datetime | None = Field(default=None, nullable=True)
    assistant_name: str | None = Field(default=None, nullable=True)
