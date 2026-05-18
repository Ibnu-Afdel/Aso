"""Rate limit backends: in-memory (single process) or Redis (multi-worker)."""

import time
from typing import Protocol

from redis.asyncio import Redis


class RateLimitBackend(Protocol):
    """Protocol for rate limit storage. Use in-memory for dev, Redis for production."""

    async def is_allowed(self, user_id: int, limit_per_minute: int) -> bool:
        """Check if user is within limit and increment. Returns True if allowed."""
        ...


class InMemoryBackend:
    """In-memory backend. Works for single process; use Redis for multi-worker."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[int, int], int] = {}

    async def is_allowed(self, user_id: int, limit_per_minute: int) -> bool:
        bucket = int(time.time() // 60)
        key = (user_id, bucket)
        count = self._buckets.get(key, 0) + 1
        self._buckets[key] = count
        return count <= limit_per_minute


class RedisBackend:
    """Redis backend. Use for production with multiple workers/replicas."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url)
        self._key_prefix = "ratelimit:bot"
        self._ttl_seconds = 120  # 2 min, covers bucket boundaries

    def _key(self, user_id: int) -> str:
        bucket = int(time.time() // 60)
        return f"{self._key_prefix}:{user_id}:{bucket}"

    async def is_allowed(self, user_id: int, limit_per_minute: int) -> bool:
        try:
            key = self._key(user_id)
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._ttl_seconds)
            results = await pipe.execute()
            count = results[0]
            return count <= limit_per_minute
        except Exception:
            # Fail open: allow requests if Redis is unavailable
            return True
