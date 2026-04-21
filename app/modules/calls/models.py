from datetime import datetime

from sqlalchemy import BigInteger, Column
from sqlmodel import Field

from app.core.models import BaseModel
from app.modules.calls.schema import Speaker


class CallSession(BaseModel, table=True):
    __tablename__ = "call_session"

    task_id: int = Field(foreign_key="task.id", nullable=False, index=True, unique=True)
    start_time: datetime = Field(default_factory=datetime.now, nullable=False)
    duration: int | None = Field(default=None, nullable=True)
    recording_uri: str | None = Field(default=None, nullable=True)
    local_recording_path: str | None = Field(default=None, nullable=True)
    # BIGINT so heavy usage (>2.1 B tokens per column) never overflows INTEGER.
    input_audio_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    output_audio_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    input_text_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    output_text_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))


class LogLine(BaseModel, table=True):
    __tablename__ = "log_line"

    session_id: int = Field(foreign_key="call_session.id", nullable=False, index=True)
    timestamp: datetime = Field(default_factory=datetime.now, nullable=False)
    speaker: Speaker = Field(nullable=False)
    text: str = Field(nullable=False)
    detected_intent: str | None = Field(default=None, nullable=True)
