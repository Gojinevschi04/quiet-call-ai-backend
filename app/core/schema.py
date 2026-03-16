from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str
    require_reauth: bool = False


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
