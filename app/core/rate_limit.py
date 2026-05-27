import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

MAX_TRACKED_IPS = 10_000
SWEEP_EVERY_REQUESTS = 500


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP address.

    Set RATE_LIMIT_PER_MINUTE=0 to disable rate limiting (useful for tests).

    Memory-safe: sweeps stale IPs every SWEEP_EVERY_REQUESTS requests and caps
    the tracked-IP map at MAX_TRACKED_IPS entries so an attacker spinning up
    fresh source IPs can't grow the dict unbounded.
    """

    def __init__(self, app, max_requests: int | None = None) -> None:  # noqa: ANN001
        super().__init__(app)
        self.max_requests = max_requests if max_requests is not None else settings.RATE_LIMIT_PER_MINUTE
        self.window = 60  # seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._requests_since_sweep = 0

    def _sweep_stale_entries(self, now: float) -> None:
        """Drop IPs whose window has fully elapsed; enforce MAX_TRACKED_IPS cap."""
        stale_cutoff = now - self.window
        expired_ips = [
            ip for ip, timestamps in self._requests.items() if not timestamps or timestamps[-1] < stale_cutoff
        ]
        for ip in expired_ips:
            del self._requests[ip]

        # If an attacker cycles IPs faster than the sweep, evict the oldest.
        if len(self._requests) > MAX_TRACKED_IPS:
            sorted_by_age = sorted(
                self._requests.items(),
                key=lambda entry: entry[1][-1] if entry[1] else 0,
            )
            overflow = len(self._requests) - MAX_TRACKED_IPS
            for ip, _ in sorted_by_age[:overflow]:
                del self._requests[ip]

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if self.max_requests <= 0:
            return await call_next(request)
        if request.url.path in ("/health",) or request.url.path.startswith("/webhooks"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        self._requests_since_sweep += 1
        if self._requests_since_sweep >= SWEEP_EVERY_REQUESTS:
            self._sweep_stale_entries(now)
            self._requests_since_sweep = 0

        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < self.window]

        if len(self._requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
