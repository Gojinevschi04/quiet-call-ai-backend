import asyncio
from functools import partial

import httpx
from twilio.rest import Client
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.core.config import settings
from app.core.constants import CALL_ANSWER_TIMEOUT_SECONDS, GATHER_TIMEOUT_SECONDS
from app.core.logging import get_logger
from app.integrations.interfaces import IVoiceProvider

logger = get_logger(__name__)

MAX_CALL_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# Google WaveNet voices for ru/ro sound more natural than Polly
LANGUAGE_CONFIG = {
    "en": {"gather_lang": "en-US", "voice": "Polly.Joanna", "say_lang": "en-US"},
    "ru": {"gather_lang": "ru-RU", "voice": "Google.ru-RU-Wavenet-A", "say_lang": "ru-RU"},
    "ro": {"gather_lang": "ro-RO", "voice": "Google.ro-RO-Wavenet-B", "say_lang": "ro-RO"},
}

# TODO: production — replace with Redis pub/sub or a shared message broker. Module-level
# dicts are acceptable for MVP (single-worker deployment) but won't work with multiple
# uvicorn workers. Entries are cleaned up after each call in the finally block.
_gather_results: dict[str, asyncio.Future] = {}

# Store language per call for webhooks to use
# TODO: production — same as _gather_results, move to Redis for multi-worker support.
_call_languages: dict[str, str] = {}


def set_gather_result(call_sid: str, speech_text: str) -> None:
    """Called by the webhook when Twilio sends gather results."""
    if call_sid in _gather_results and not _gather_results[call_sid].done():
        _gather_results[call_sid].set_result(speech_text)


class TwilioAdapter(IVoiceProvider):
    def __init__(self) -> None:
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self._from_phone = settings.TWILIO_PHONE_NUMBER

    async def _run_sync(self, func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def initiate_call(self, to_phone: str, callback_url: str) -> str:
        """Initiate call with retry logic for busy/no-answer."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_CALL_RETRIES + 1):
            try:
                logger.info("Initiating call to %s (attempt %d/%d)", to_phone, attempt, MAX_CALL_RETRIES)
                call = await self._run_sync(
                    self._client.calls.create,
                    to=to_phone,
                    from_=self._from_phone,
                    url=callback_url,
                    record=True,
                    status_callback=f"{callback_url}/status",
                    status_callback_event=["initiated", "ringing", "answered", "completed"],
                    machine_detection="DetectMessageEnd",
                )
                logger.info("Call initiated with SID: %s", call.sid)
                return call.sid
            except Exception as e:
                last_error = e
                logger.warning("Call attempt %d failed: %s", attempt, str(e))
                if attempt < MAX_CALL_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        raise last_error or RuntimeError("Call initiation failed after all retries")

    async def initiate_call_with_twiml(
        self,
        to_phone: str,
        twiml: str,
        status_callback_url: str,
        recording_callback_url: str,
    ) -> str:
        """Initiate outbound call using inline TwiML (used by realtime streaming path)."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_CALL_RETRIES + 1):
            try:
                logger.info("Initiating realtime call to %s (attempt %d/%d)", to_phone, attempt, MAX_CALL_RETRIES)
                call = await self._run_sync(
                    self._client.calls.create,
                    to=to_phone,
                    from_=self._from_phone,
                    twiml=twiml,
                    record=True,
                    status_callback=status_callback_url,
                    status_callback_event=["initiated", "ringing", "answered", "completed"],
                    recording_status_callback=recording_callback_url,
                    recording_status_callback_event=["completed"],
                )
                logger.info("Realtime call initiated with SID: %s", call.sid)
                return call.sid
            except Exception as e:
                last_error = e
                logger.warning("Realtime call attempt %d failed: %s", attempt, str(e))
                if attempt < MAX_CALL_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        raise last_error or RuntimeError("Realtime call initiation failed after all retries")

    async def hangup(self, call_sid: str) -> None:
        logger.info("Hanging up call %s", call_sid)
        try:
            await self._run_sync(
                self._client.calls(call_sid).update,
                status="completed",
            )
        except Exception as e:
            logger.warning("Failed to hang up call %s: %s", call_sid, e)

    async def get_call_status(self, call_sid: str) -> str:
        call = await self._run_sync(self._client.calls(call_sid).fetch)
        return call.status

    async def get_recording_url(self, call_sid: str) -> str | None:
        recordings = await self._run_sync(
            self._client.recordings.list,
            call_sid=call_sid,
            limit=1,
        )
        if not recordings:
            return None
        return f"https://api.twilio.com{recordings[0].uri.replace('.json', '.mp3')}"

    async def play_audio(self, call_sid: str, audio_bytes: bytes) -> None:
        """Update the live call with TwiML that speaks text and gathers response.

        For MVP, we use Twilio's <Say> verb instead of streaming OpenAI TTS audio.
        The audio_bytes param is ignored — we extract text from the conversation
        and let Twilio speak it. The caller will use say_and_gather() instead.
        """
        # Interface compatibility — real work done by say_and_gather()

    async def say_and_gather(
        self, call_sid: str, text: str, callback_url: str, language: str = "en"
    ) -> str:
        """Speak text to the callee using Twilio TTS and wait for their response.

        Uses Twilio's <Say> + <Gather> TwiML, then waits for the webhook to
        deliver the speech result via set_gather_result().
        """
        lang_cfg = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["en"])

        clean_text = text.replace("[OBJECTIVE_ACHIEVED]", "").replace("[OBJECTIVE_FAILED]", "").strip()
        if not clean_text:
            fallback = {"en": "Thank you. Goodbye.", "ru": "Спасибо. До свидания.", "ro": "Mulțumesc. La revedere."}
            clean_text = fallback.get(language, "Thank you. Goodbye.")

        _call_languages[call_sid] = language

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        _gather_results[call_sid] = future

        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{callback_url}/gather",
            timeout=GATHER_TIMEOUT_SECONDS,
            speech_timeout="auto",
            language=lang_cfg["gather_lang"],
        )
        gather.say(clean_text, voice=lang_cfg["voice"], language=lang_cfg["say_lang"])
        response.append(gather)
        no_response = {"en": "I didn't hear a response.", "ru": "Я не услышал ответа.", "ro": "Nu am auzit un răspuns."}
        response.say(no_response.get(language, no_response["en"]), voice=lang_cfg["voice"])
        response.redirect(f"{callback_url}")

        logger.info("Speaking to call %s: %.60s...", call_sid, clean_text)

        try:
            await self._run_sync(
                self._client.calls(call_sid).update,
                twiml=str(response),
            )
        except Exception as e:
            logger.error("Failed to update call %s with TwiML: %s", call_sid, e)
            _gather_results.pop(call_sid, None)
            raise

        try:
            speech_text = await asyncio.wait_for(future, timeout=CALL_ANSWER_TIMEOUT_SECONDS)
            logger.info("Received speech from call %s: %.60s...", call_sid, speech_text)
            return speech_text
        except TimeoutError:
            logger.warning("No speech received from call %s within timeout", call_sid)
            return ""
        finally:
            _gather_results.pop(call_sid, None)

    async def listen(self, call_sid: str, timeout: int = 10) -> bytes:
        """Legacy listen method — not used in webhook-driven flow."""
        logger.debug("Listening on call %s (timeout=%ds)", call_sid, timeout)
        await asyncio.sleep(timeout)
        return b""

    async def get_recording_audio(self, recording_url: str) -> bytes:
        """Download recording audio bytes from Twilio."""
        logger.debug("Downloading recording from %s", recording_url)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                recording_url,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content

    @staticmethod
    def generate_gather_twiml(audio_text: str, callback_url: str) -> str:
        """Generate TwiML with Say + Gather for the webhook response."""
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{callback_url}/gather",
            timeout=GATHER_TIMEOUT_SECONDS,
            speech_timeout="auto",
            language="en-US",
        )
        gather.say(audio_text, voice="Polly.Joanna")
        response.append(gather)
        response.say("I didn't hear anything. Goodbye.", voice="Polly.Joanna")
        return str(response)
