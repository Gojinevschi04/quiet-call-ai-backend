import asyncio

from fastapi import APIRouter

from app.core.logging import get_logger
from app.modules.feedback.schema import FeedbackRequest, FeedbackResponse
from app.modules.notifications.email_service import EmailService

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/")
async def submit_feedback(data: FeedbackRequest) -> FeedbackResponse:
    """Public endpoint — no auth required."""
    email_service = EmailService()
    asyncio.create_task(
        email_service.send_feedback(data.name, data.email, data.message)
    )
    return FeedbackResponse(message="Thank you for your feedback! We'll get back to you soon.")
