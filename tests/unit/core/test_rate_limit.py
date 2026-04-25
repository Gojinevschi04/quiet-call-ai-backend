import time

from app.core.rate_limit import MAX_TRACKED_IPS, RateLimitMiddleware


class _StubApp:
    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        return None


def _make_middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(_StubApp(), max_requests=60)


def test_sweep_evicts_stale_ips() -> None:
    """Regression: IPs whose 60 s window has fully elapsed get dropped."""
    middleware = _make_middleware()
    now = time.time()
    middleware._requests["fresh"] = [now]
    middleware._requests["stale"] = [now - 120]
    middleware._requests["borderline"] = [now - 59]

    middleware._sweep_stale_entries(now)

    assert "fresh" in middleware._requests
    assert "borderline" in middleware._requests
    assert "stale" not in middleware._requests


def test_sweep_enforces_max_tracked_ips_cap() -> None:
    """Regression: attacker cycling IPs faster than sweep can't grow dict unbounded."""
    middleware = _make_middleware()
    now = time.time()
    for ip_index in range(MAX_TRACKED_IPS + 10):
        middleware._requests[f"ip-{ip_index}"] = [now - (ip_index % 30)]

    middleware._sweep_stale_entries(now)

    assert len(middleware._requests) <= MAX_TRACKED_IPS
