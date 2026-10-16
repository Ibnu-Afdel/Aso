"""`memory` cache driver unit tests (T-44): process dict, monotonic-clock expiry."""

from __future__ import annotations

import asyncio

from aso.cache.manager import CacheStore
from aso.cache.memory import MemoryDriver


def _store() -> CacheStore:
    return CacheStore(MemoryDriver(), "test_")


async def test_put_then_get_round_trips_json_values():
    store = _store()
    await store.put("k", {"a": [1, 2, 3], "b": "x"})
    assert await store.get("k") == {"a": [1, 2, 3], "b": "x"}


async def test_get_missing_key_returns_default():
    store = _store()
    assert await store.get("nope") is None
    assert await store.get("nope", "fallback") == "fallback"


async def test_ttl_expires_the_value():
    store = _store()
    await store.put("k", "v", ttl=1)
    assert await store.get("k") == "v"
    await asyncio.sleep(1.1)
    assert await store.get("k", "gone") == "gone"


async def test_forget_removes_the_key():
    store = _store()
    await store.put("k", "v")
    assert await store.forget("k") is True
    assert await store.forget("k") is False
    assert await store.get("k") is None


async def test_increment_and_decrement_start_from_zero_and_persist_without_ttl():
    store = _store()
    assert await store.increment("n") == 1
    assert await store.increment("n") == 2
    assert await store.decrement("n") == 1
    assert await store.decrement("n", amount=5) == -4


async def test_increment_preserves_an_existing_ttl():
    store = _store()
    await store.put("n", 0, ttl=60)
    await store.increment("n")
    await store.increment("n")
    assert await store.get("n") == 2


async def test_remember_runs_the_callback_only_once():
    store = _store()
    calls = {"count": 0}

    def compute():
        calls["count"] += 1
        return "computed"

    assert await store.remember("k", 60, compute) == "computed"
    assert await store.remember("k", 60, compute) == "computed"
    assert calls["count"] == 1


async def test_remember_awaits_an_async_callback():
    store = _store()

    async def compute():
        return "async-computed"

    assert await store.remember("k", 60, compute) == "async-computed"


async def test_non_json_serialisable_value_raises_immediately():
    store = _store()

    class NotSerialisable:
        pass

    try:
        # The class itself (not an instance): no `__dict__` to fall back to, so even FastAPI's
        # very permissive `jsonable_encoder` gives up.
        await store.put("k", NotSerialisable)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")


async def test_flush_clears_every_key_in_the_store():
    store = _store()
    await store.put("a", 1)
    await store.put("b", 2)
    await store.flush()
    assert await store.get("a") is None
    assert await store.get("b") is None


async def test_add_sets_the_key_only_when_absent():
    store = _store()
    assert await store.add("k", "first") is True
    assert await store.add("k", "second") is False
    assert await store.get("k") == "first"


async def test_add_succeeds_again_once_the_ttl_has_expired():
    store = _store()
    await store.put("k", "v", ttl=1)
    await asyncio.sleep(1.1)
    assert await store.add("k", "fresh") is True
    assert await store.get("k") == "fresh"


async def test_add_is_atomic_under_concurrent_calls():
    store = _store()
    results = await asyncio.gather(*(store.add("lock", "winner") for _ in range(20)))
    assert results.count(True) == 1
    assert results.count(False) == 19


async def test_prefix_namespaces_keys_so_two_stores_do_not_collide():
    driver = MemoryDriver()
    one = CacheStore(driver, "one_")
    two = CacheStore(driver, "two_")
    await one.put("k", "from-one")
    await two.put("k", "from-two")
    assert await one.get("k") == "from-one"
    assert await two.get("k") == "from-two"
