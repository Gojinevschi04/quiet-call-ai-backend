"""Cost estimation for calls.

OpenAI Realtime token pricing (USD per 1M tokens). Twilio per-minute rates are
configurable — defaults target Moldova mobile terminating via international
trunk (~$0.30/min voice, $0.004/min Media Streams).

Kept in sync with the FE copy in `src/types/call.ts`.
"""

from app.core.config import settings

OPENAI_REALTIME_PRICE_PER_MILLION_USD = {
    "input_audio": 32.0,
    "output_audio": 64.0,
    "input_text": 4.0,
    "output_text": 16.0,
}

TOKENS_PER_MILLION = 1_000_000
SECONDS_PER_MINUTE = 60
COST_DECIMAL_PLACES = 4


def estimate_cost_usd(
    input_audio_tokens: int,
    output_audio_tokens: int,
    input_text_tokens: int,
    output_text_tokens: int,
) -> float:
    """Compute the estimated USD cost for a token breakdown."""
    rates = OPENAI_REALTIME_PRICE_PER_MILLION_USD
    total = (
        input_audio_tokens * rates["input_audio"]
        + output_audio_tokens * rates["output_audio"]
        + input_text_tokens * rates["input_text"]
        + output_text_tokens * rates["output_text"]
    ) / TOKENS_PER_MILLION
    return round(total, COST_DECIMAL_PLACES)


def estimate_twilio_cost_usd(duration_seconds: int) -> float:
    """Estimate Twilio voice + Media Streams cost for a call of the given duration."""
    if duration_seconds <= 0:
        return 0.0
    duration_minutes = duration_seconds / SECONDS_PER_MINUTE
    rate_per_min = settings.TWILIO_VOICE_RATE_PER_MIN_USD + settings.TWILIO_MEDIA_STREAM_RATE_PER_MIN_USD
    return round(duration_minutes * rate_per_min, COST_DECIMAL_PLACES)


def estimate_total_cost_usd(
    duration_seconds: int,
    input_audio_tokens: int,
    output_audio_tokens: int,
    input_text_tokens: int,
    output_text_tokens: int,
) -> float:
    """Twilio + OpenAI combined per-call cost."""
    return round(
        estimate_twilio_cost_usd(duration_seconds)
        + estimate_cost_usd(input_audio_tokens, output_audio_tokens, input_text_tokens, output_text_tokens),
        COST_DECIMAL_PLACES,
    )
