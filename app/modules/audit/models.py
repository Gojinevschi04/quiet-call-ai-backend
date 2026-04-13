from sqlmodel import Field

from app.core.models import BaseModel


class AuditLog(BaseModel, table=True):
    __tablename__ = "audit_log"

    user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    action: str = Field(nullable=False, index=True)
    target_type: str = Field(nullable=False)
    target_id: int | None = Field(default=None, nullable=True)
    details: str | None = Field(default=None, nullable=True)
