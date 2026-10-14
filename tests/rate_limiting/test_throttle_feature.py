"""End-to-end `throttle:` middleware tests through the real ASGI stack (T-11, T-44).

Fixture app: `tests/fixtures/throttle_app`. `/ping` uses `throttle:2,1` (2/minute, unnamed);
`/ping-named` uses `throttle:api` (a named limiter registered in `bootstrap/app.py`, keyed by
client IP); `/ping-unlimited` uses `throttle:none` (`Limit.none()`); `/api/ping` is the same
numeric limit on the stateless API group (JSON 429 instead of the HTML/Inertia error page).
"""

from __future__ import annotations

import httpx2 as httpx


async def test_requests_within_the_limit_succeed_with_rate_limit_headers(client: httpx.AsyncClient):
    r = await client.get("/ping")
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "2"
    assert r.headers["X-RateLimit-Remaining"] == "1"

    r = await client.get("/ping")
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Remaining"] == "0"


async def test_exceeding_the_limit_raises_429_with_retry_after(client: httpx.AsyncClient):
    await client.get("/ping")
    await client.get("/ping")
    r = await client.get("/ping")
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}
    retry_after = int(r.headers["Retry-After"])
    assert 0 < retry_after <= 60


async def test_api_group_renders_json_429(client: httpx.AsyncClient):
    await client.get("/api/ping")
    await client.get("/api/ping")
    r = await client.get("/api/ping")
    assert r.status_code == 429
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"message": "Too Many Attempts."}
    assert "Retry-After" in r.headers


async def test_named_limiter_is_resolved_from_ratelimiter_for(client: httpx.AsyncClient):
    """`/ping-named` uses `throttle:api`, registered as `Limit.per_minute(3).by(client_ip)`."""
    for _ in range(3):
        r = await client.get("/ping-named")
        assert r.status_code == 200
    r = await client.get("/ping-named")
    assert r.status_code == 429


async def test_limit_none_never_throttles(client: httpx.AsyncClient):
    for _ in range(10):
        r = await client.get("/ping-unlimited")
        assert r.status_code == 200
    # Limit.none() never calls RateLimiter.hit(), so no X-RateLimit headers either.
    assert "X-RateLimit-Limit" not in r.headers


async def test_unregistered_named_limiter_raises_clear_error(client: httpx.AsyncClient):
    from fastogram.rate_limiting import Limit, RateLimiter

    RateLimiter.for_("ghost-undefined", lambda request: Limit.per_minute(1))
    # The route under test never references "ghost-undefined"; this test instead exercises the
    # middleware's own resolution function directly against a name that truly is not registered.
    from fastogram.rate_limiting.middleware import _resolve_limit

    class _FakeRequest:
        pass

    try:
        _resolve_limit(_FakeRequest(), ("totally-unregistered",))
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "totally-unregistered" in str(exc)
