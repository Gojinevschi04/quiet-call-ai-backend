from pydantic import BaseModel, EmailStr, field_validator


class FeedbackRequest(BaseModel):
    name: str
    email: EmailStr
    message: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Name is required")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Message must be at least 5 characters")
        if len(v) > 5000:
            raise ValueError("Message must be at most 5000 characters")
        return v


class FeedbackResponse(BaseModel):
    message: str
