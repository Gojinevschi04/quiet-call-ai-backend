import logging
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LOG_LEVEL: str | int = Field(default=logging.INFO)
    STORAGE_PATH: str = "storage"

    DB_HOST: str = ""
    DB_PORT: str = ""
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASS: str = ""

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TTS_MODEL: str = "tts-1"
    OPENAI_TTS_VOICE: str = "nova"
    OPENAI_STT_MODEL: str = "whisper-1"

    BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:3000"
    RATE_LIMIT_PER_MINUTE: int = 60
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@quietcall.ai"
    EMAIL_FROM_NAME: str = "Quiet Call AI"
    EMAIL_ENABLED: bool = False
    FEEDBACK_EMAILS: str = ""  # Comma-separated list of emails to receive feedback
    TEST_PHONE_OVERRIDE: str = ""  # When set, all calls go to this number instead of task's target_phone

    USE_REALTIME_API: bool = False
    OPENAI_REALTIME_MODEL: str = "gpt-realtime"
    OPENAI_REALTIME_VOICE: str = "alloy"
    REALTIME_VAD_MODE: str = "semantic_vad"
    REALTIME_VAD_EAGERNESS: str = "medium"

    MAX_CONCURRENT_CALLS: int = 10
    AI_DISCLOSURE_REQUIRED: bool = True
    MAX_CALL_DURATION_SECONDS: int = 300
    CALL_WINDOW_START_HOUR: int = 9
    CALL_WINDOW_END_HOUR: int = 20

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        extra="ignore",
        populate_by_name=True,
    )

    @computed_field
    def DB_URL(self) -> str:  # noqa: N802
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field
    def STORAGE_DIR(self) -> Path:  # noqa: N802
        return Path(__file__).parent.parent.parent / self.STORAGE_PATH


settings = Settings()
