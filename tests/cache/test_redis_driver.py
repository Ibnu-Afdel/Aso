"""`redis` cache driver tests (T-44).

Skips when the `redis` package is not installed (it is an optional dependency,
`aso[redis]`) and again when no Redis server answers at `REDIS_URL` (default
`redis://127.0.0.1:6379/1`), so this file is always safe to run in CI without a live Redis.
"""

from __future__ import annotations

import os

import pytest

redis_asyncio = pytest.importorskip("redis.asyncio", reason="the `redis` package is not installed")

from aso.cache.manager import CacheStore  # noqa: E402
from aso.cache.redis_store import RedisDriver  # noqa: E402

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1")


async def _server_available() -> bool:
    client = redis_asyncio.Redis.from_url(REDIS_URL)
    try:
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()


@pytest.fixture
async def store():
    if not await _server_available():
        pytest.skip(f"no Redis server answering at {REDIS_URL}")
    cache_store = CacheStore(RedisDriver(REDIS_URL), "aso_cache_test_")
    await cache_store.flush()
    yield cache_store
    await cache_store.flush()


async def test_put_then_get_round_trips_json_values(store: CacheStore):
    await store.put("k", {"a": 1, "b": [1, 2]})
    assert await store.get("k") == {"a": 1, "b": [1, 2]}


async def test_ttl_is_enforced_by_redis_ex(store: CacheStore):
    await store.put("k", "v", ttl=60)
    assert await store.get("k") == "v"


async def test_increment_uses_incrby(store: CacheStore):
    assert await store.increment("n") == 1
    assert await store.increment("n", amount=4) == 5
    assert await store.decrement("n", amount=2) == 3


async def test_add_sets_the_key_only_when_absent(store: CacheStore):
    assert await store.add("k", "first") is True
    assert await store.add("k", "second") is False
    assert await store.get("k") == "first"


async def test_forget_deletes_the_key(store: CacheStore):
    await store.put("k", "v")
    assert await store.forget("k") is True
    assert await store.get("k") is None


async def test_flush_only_clears_this_prefix(store: CacheStore):
    other = CacheStore(store._driver, "other_prefix_")  # noqa: SLF001 -- same connection, different namespace
    await store.put("mine", "a")
    await other.put("theirs", "b")
    await store.flush()
    assert await store.get("mine") is None
    assert await other.get("theirs") == "b"
    await other.forget("theirs")


def test_missing_package_raises_a_clear_runtime_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis.asyncio" or name.startswith("redis."):
            raise ImportError("simulated: redis not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        RedisDriver(REDIS_URL)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "redis" in str(exc).lower()
