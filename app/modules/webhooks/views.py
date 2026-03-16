from typing import Annotated

from fastapi import APIRouter, Depends, Form, Response

from app.core.logging import get_logger
from app.integrations.twilio_adapter import set_gather_result
from app.modules.calls.repository import CallSessionRepository
from app.modules.tasks.repository import TaskRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/calls/{task_id}")
async def twilio_call_callback(
    task_id: int,
    task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
    CallSid: str = Form(default=""),
    CallStatus: str = Form(default=""),
) -> Response:
    """TwiML callback — Twilio requests this when the call connects.

    Returns minimal TwiML to keep the call alive. The CallManager controls
    the conversation by updating the call with new TwiML via say_and_gather().
    """
    logger.info("Twilio callback for task %d, SID=%s, status=%s", task_id, CallSid, CallStatus)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Pause length=\"30\"/>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/calls/{task_id}/gather")
async def twilio_gather_callback(
    task_id: int,
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0"),
    CallSid: str = Form(default=""),
) -> Response:
    """Receives Twilio Gather speech result and delivers it to the CallManager.

    The CallManager's say_and_gather() is waiting on an asyncio Future.
    We resolve that future here with the speech text, so the dialog loop continues.
    """
    logger.info(
        "Twilio gather for task %d: SID=%s, speech='%s', confidence=%s",
        task_id,
        CallSid,
        SpeechResult[:100] if SpeechResult else "",
        Confidence,
    )

    if CallSid:
        set_gather_result(CallSid, SpeechResult or "")

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Pause length=\"30\"/>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/calls/{task_id}/status")
async def twilio_status_callback(
    task_id: int,
    task_repository: Annotated[TaskRepository, Depends(TaskRepository)],
    call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
    CallSid: str = Form(default=""),
    CallStatus: str = Form(default=""),
    CallDuration: str = Form(default="0"),
) -> Response:
    """Twilio status callback — receives call state changes."""
    logger.info(
        "Twilio status update for task %d: SID=%s, status=%s, duration=%s",
        task_id,
        CallSid,
        CallStatus,
        CallDuration,
    )

    if CallStatus == "completed":
        call_session = await call_session_repository.get_by_task_id(task_id)
        if call_session and not call_session.duration:
            try:
                call_session.duration = int(CallDuration) if CallDuration else 0
            except (ValueError, TypeError):
                call_session.duration = 0
                logger.warning("Malformed CallDuration for task %d: %s", task_id, CallDuration)
            await call_session_repository.update(call_session)
            logger.info("Updated call session duration for task %d: %ss", task_id, CallDuration)

    elif CallStatus in ("busy", "no-answer", "canceled", "failed"):
        logger.warning("Call failed for task %d with status: %s", task_id, CallStatus)
        call_session = await call_session_repository.get_by_task_id(task_id)
        if call_session:
            call_session.duration = 0
            await call_session_repository.update(call_session)

    return Response(content="<Response/>", media_type="application/xml")


@router.post("/calls/{task_id}/recording")
async def twilio_recording_callback(
    task_id: int,
    call_session_repository: Annotated[CallSessionRepository, Depends(CallSessionRepository)],
    RecordingUrl: str = Form(default=""),
    RecordingDuration: str = Form(default="0"),
) -> Response:
    """Twilio recording callback — receives the recording URL after call ends."""
    logger.info(
        "Twilio recording for task %d: url=%s, duration=%s",
        task_id,
        RecordingUrl,
        RecordingDuration,
    )

    if RecordingUrl:
        call_session = await call_session_repository.get_by_task_id(task_id)
        if call_session:
            call_session.recording_uri = RecordingUrl
            await call_session_repository.update(call_session)
            logger.info("Saved recording URL for task %d", task_id)

    return Response(content="<Response/>", media_type="application/xml")
