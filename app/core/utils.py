from fastapi import Request


def get_request_language(request: Request) -> str:
    """Extract UI language code from the Accept-Language header.

    Returns a 2-letter language code (e.g., "en", "ru", "ro").
    Falls back to "en" if the header is missing or unparseable.
    """
    lang = request.headers.get("accept-language", "en")
    return lang.split(",")[0].split("-")[0].strip()[:2]
