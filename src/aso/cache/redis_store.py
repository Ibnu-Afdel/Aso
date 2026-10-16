"""`redis` cache driver (T-44): `redis.asyncio`, `SET ... EX` / `GET` / `INCRBY` / `DEL`.

Imported lazily -- only touched when a store actually uses the `redis` driver, so the `redis`
package stays an optional dependency (`aso[redis]`). Tests that need a live server skip
themselves when one is not reachable (see `tests/cache/test_redis_driver.py`).
"""

from __future__ import annotations

from typing import Any


class RedisDriver:
    def __init__(self, url: str) -> None:
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError(
                'The "redis" cache store needs the `redis` package. Install it with '
                '`uv add "aso[redis]"` (or `pip install redis`).'
            ) from exc
        self._client: Any = Redis.from_url(url, decode_responses=True)

    async def get_raw(self, key: str) -> str | None:
        return await self._client.get(key)

    async def put_raw(self, key: str, raw: str, ttl: int | None) -> None:
        if ttl is not None:
            await self._client.set(key, raw, ex=ttl)
        else:
            await self._client.set(key, raw)

    async def add_raw(self, key: str, raw: str, ttl: int | None) -> bool:
        """`SET key value NX [EX ttl]`: Redis's own atomic check-and-set (T-44)."""
        result = await self._client.set(key, raw, nx=True, ex=ttl)
        return bool(result)

    async def forget(self, key: str) -> bool:
        deleted = await self._client.delete(key)
        return bool(deleted)

    async def increment_raw(self, key: str, amount: int) -> int:
        return int(await self._client.incrby(key, amount))

    async def flush(self, prefix: str = "") -> None:
        """Delete only this store's keys (`SCAN` + `DEL`), never `FLUSHDB` -- a shared Redis may
        hold data for other stores or other apps."""
        pattern = f"{prefix}*" if prefix else "*"
        cursor = 0
        while True:
            cursor, keys = await self._client.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                await self._client.delete(*keys)
            if cursor == 0:
                break
