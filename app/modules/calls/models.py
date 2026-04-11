from datetime import datetime

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
    input_audio_tokens: int = Field(default=0, nullable=False)
    output_audio_tokens: int = Field(default=0, nullable=False)
    input_text_tokens: int = Field(default=0, nullable=False)
    output_text_tokens: int = Field(default=0, nullable=False)


class LogLine(BaseModel, table=True):
    __tablename__ = "log_line"

    session_id: int = Field(foreign_key="call_session.id", nullable=False, index=True)
    timestamp: datetime = Field(default_factory=datetime.now, nullable=False)
    speaker: Speaker = Field(nullable=False)
    text: str = Field(nullable=False)
    detected_intent: str | None = Field(default=None, nullable=True)
