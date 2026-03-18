"""Utility to generate demo phone call audio using text-to-speech.

Uses Microsoft Edge TTS (edge-tts) for natural-sounding neural voices
with distinct speakers for Agent and Caller.
"""

import asyncio
import io
import math
import random
import struct
import wave

from app.core.logging import get_logger

logger = get_logger(__name__)

# Neural voices — natural, conversational tone
VOICE_AGENT = "en-US-EmmaNeural"  # Female, cheerful, conversational
VOICE_CALLER = "en-US-BrianNeural"  # Male, approachable, casual


def generate_demo_wav(duration_seconds: int = 5, sample_rate: int = 16000) -> bytes:
    """Generate a silent WAV placeholder (used when no transcript is available)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)

        total_samples = sample_rate * duration_seconds
        frames = []
        random.seed(42)

        for i in range(total_samples):
            t = i / sample_rate
            hum = 80 * math.sin(2 * math.pi * 60 * t)
            noise = random.gauss(0, 60)
            fade = min(t / 0.3, 1.0) * min((duration_seconds - t) / 0.3, 1.0) if duration_seconds > 0 else 0
            value = int(fade * (hum + noise))
            value = max(-32768, min(32767, value))
            frames.append(struct.pack("<h", value))

        wav.writeframes(b"".join(frames))

    return buf.getvalue()


async def _synthesize_line(text: str, voice: str) -> bytes:
    """Synthesize a single line of text using Edge TTS."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    mp3_buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_buf.write(chunk["data"])
    return mp3_buf.getvalue()


async def generate_demo_conversation_mp3_async(
    lines: list[tuple[str, str]],
) -> bytes:
    """Generate an MP3 conversation with two distinct neural voices.

    Args:
        lines: List of (speaker, text) tuples.
               Speaker should be "agent"/"Agent" or "interlocutor"/"Caller"/anything else.

    Returns:
        MP3 audio bytes of the full conversation.
    """
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        logger.warning("edge-tts not installed — run 'poetry add edge-tts'. Falling back to silent WAV.")
        return generate_demo_wav(duration_seconds=10)

    parts: list[bytes] = []

    for speaker, text in lines:
        clean_text = text.replace("[OBJECTIVE_ACHIEVED]", "").replace("[OBJECTIVE_FAILED]", "").strip()
        if not clean_text:
            continue

        voice = VOICE_AGENT if speaker.lower() == "agent" else VOICE_CALLER

        try:
            mp3_bytes = await _synthesize_line(clean_text, voice)
            if mp3_bytes:
                parts.append(mp3_bytes)
                logger.debug("TTS [%s]: %.40s... (%d bytes)", voice, clean_text, len(mp3_bytes))
        except Exception as e:
            logger.warning("Failed TTS for line: %.50s — %s", clean_text, e)
            continue

    if not parts:
        logger.warning("No TTS parts generated, falling back to silent WAV")
        return generate_demo_wav(duration_seconds=5)

    logger.info("Generated %d TTS segments, total %d bytes", len(parts), sum(len(p) for p in parts))
    return b"".join(parts)


def generate_demo_conversation_mp3(
    lines: list[tuple[str, str]],
) -> bytes:
    """Sync wrapper for generate_demo_conversation_mp3_async.

    Detects whether an event loop is already running and handles accordingly.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Called from run_in_executor — needs its own event loop in this thread
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(generate_demo_conversation_mp3_async(lines))
        finally:
            new_loop.close()
    else:
        return asyncio.run(generate_demo_conversation_mp3_async(lines))
