"""`RateLimiter` (T-44, T-38): named limiters + the cache-backed hit counter.

Mirrors Laravel's scheme exactly: `hit()` increments `<key>` and sets `<key>:timer` once; both
live in the default cache store, so limits are only as shared as that store (T-44 "How it
works"). Everything here is classmethods, like Laravel's static `RateLimiter::` facade.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

from aso.cache import cache

_limiters: dict[str, Callable[[Any], Any]] = {}


class RateLimiter:
    @classmethod
    def for_(cls, name: str, callback: Callable[[Any], Any]) -> None:
        """Register a named limiter (`RateLimiter.for_("api", lambda request: Limit...)`)."""
        _limiters[name] = callback

    @classmethod
    def limiter(cls, name: str) -> Callable[[Any], Any] | None:
        return _limiters.get(name)

    @classmethod
    async def attempts(cls, key: str) -> int:
        return int(await cache().get(key, 0) or 0)

    @classmethod
    async def remaining(cls, key: str, max_attempts: int) -> int:
        return max(0, max_attempts - await cls.attempts(key))

    @classmethod
    async def too_many_attempts(cls, key: str, max_attempts: int) -> bool:
        if await cls.attempts(key) >= max_attempts:
            if await cache().get(f"{key}:timer") is not None:
                return True
            # the decay window lapsed without the attempts counter expiring at the same instant:
            # reset it, exactly like Laravel's `tooManyAttempts()`.
            await cache().forget(key)
            return False
        return False

    @classmethod
    async def hit(cls, key: str, decay_seconds: int = 60) -> int:
        store = cache()
        timer_key = f"{key}:timer"
        if await store.get(timer_key) is None:
            await store.put(timer_key, _now() + decay_seconds, ttl=decay_seconds)
        if await store.get(key) is None:
            await store.put(key, 0, ttl=decay_seconds)
        return await store.increment(key)

    @classmethod
    async def available_in(cls, key: str) -> int:
        available_at = await cache().get(f"{key}:timer")
        if available_at is None:
            return 0
        return max(0, math.ceil(available_at - _now()))

    @classmethod
    async def clear(cls, key: str) -> None:
        store = cache()
        await store.forget(key)
        await store.forget(f"{key}:timer")


def _now() -> float:
    return time.time()


def _reset_for_tests() -> None:
    """Drop every registered named limiter. Test helper, not part of the Laravel-facing API."""
    _limiters.clear()
