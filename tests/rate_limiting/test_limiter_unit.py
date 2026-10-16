"""Unit tests for `RateLimiter` and `Limit` (T-44), against the `memory` cache store directly."""

from __future__ import annotations

from aso.config import set_config
from aso.rate_limiting import Limit, RateLimiter


async def test_hit_increments_and_too_many_attempts_trips_at_the_limit():
    set_config("app.environment", "testing")
    key = "unit:hit"
    for expected in (1, 2, 3):
        assert await RateLimiter.hit(key, decay_seconds=60) == expected
    assert await RateLimiter.too_many_attempts(key, max_attempts=3) is True
    assert await RateLimiter.too_many_attempts(key, max_attempts=4) is False


async def test_available_in_counts_down_and_clear_resets_everything():
    key = "unit:available"
    await RateLimiter.hit(key, decay_seconds=60)
    seconds = await RateLimiter.available_in(key)
    assert 0 < seconds <= 60

    await RateLimiter.clear(key)
    assert await RateLimiter.attempts(key) == 0
    assert await RateLimiter.available_in(key) == 0


async def test_remaining_counts_down_to_zero_and_never_goes_negative():
    key = "unit:remaining"
    assert await RateLimiter.remaining(key, max_attempts=2) == 2
    await RateLimiter.hit(key, decay_seconds=60)
    assert await RateLimiter.remaining(key, max_attempts=2) == 1
    await RateLimiter.hit(key, decay_seconds=60)
    await RateLimiter.hit(key, decay_seconds=60)
    assert await RateLimiter.remaining(key, max_attempts=2) == 0


async def test_for_and_limiter_register_and_fetch_named_limiters():
    callback = lambda request: Limit.per_minute(5)  # noqa: E731
    RateLimiter.for_("unit-named", callback)
    assert RateLimiter.limiter("unit-named") is callback
    assert RateLimiter.limiter("does-not-exist") is None


def test_limit_factories_and_by():
    assert Limit.per_minute(10).decay_seconds == 60
    assert Limit.per_hour(10).decay_seconds == 3600
    assert Limit.per_day(10).decay_seconds == 86400
    assert Limit.none().unlimited is True

    limit = Limit.per_minute(5).by(42)
    assert limit.key == "42"
    assert limit.max_attempts == 5
