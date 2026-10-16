"""`file` cache driver unit tests (T-44): one file per key, atomic writes, TTL, locked increments."""

from __future__ import annotations

import asyncio
import time

from aso.cache.file import FileDriver
from aso.cache.manager import CacheStore


def _store(tmp_path) -> CacheStore:
    return CacheStore(FileDriver(tmp_path), "test_")


async def test_put_then_get_round_trips_and_writes_one_file_per_key(tmp_path):
    store = _store(tmp_path)
    await store.put("k", {"a": 1})
    assert await store.get("k") == {"a": 1}
    files = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(files) == 1


async def test_ttl_expires_the_value_and_removes_the_file(tmp_path):
    store = _store(tmp_path)
    await store.put("k", "v", ttl=1)
    assert await store.get("k") == "v"
    await asyncio.sleep(1.1)
    assert await store.get("k", "gone") == "gone"
    assert not any(tmp_path.iterdir())


async def test_forget_removes_the_file(tmp_path):
    store = _store(tmp_path)
    await store.put("k", "v")
    assert await store.forget("k") is True
    assert await store.forget("k") is False


async def test_increment_is_atomic_under_concurrent_calls(tmp_path):
    store = _store(tmp_path)
    await asyncio.gather(*(store.increment("n") for _ in range(20)))
    assert await store.get("n") == 20


async def test_increment_preserves_an_existing_ttl(tmp_path):
    store = _store(tmp_path)
    await store.put("n", 0, ttl=60)
    await store.increment("n")
    value = await store.get("n")
    assert value == 1
    # the backing file must still carry an expiry, not "forever"
    driver = store._driver  # noqa: SLF001 -- white-box check of the on-disk payload
    raw_file = next(p for p in tmp_path.iterdir() if p.is_file() and not p.name.endswith(".lock"))
    import json

    payload = json.loads(raw_file.read_text())
    assert payload["expires_at"] is not None
    assert time.time() < payload["expires_at"] <= time.time() + 60
    del driver


async def test_add_sets_the_key_only_when_absent(tmp_path):
    store = _store(tmp_path)
    assert await store.add("k", "first") is True
    assert await store.add("k", "second") is False
    assert await store.get("k") == "first"


async def test_add_succeeds_again_once_the_ttl_has_expired(tmp_path):
    store = _store(tmp_path)
    await store.put("k", "v", ttl=1)
    await asyncio.sleep(1.1)
    assert await store.add("k", "fresh") is True
    assert await store.get("k") == "fresh"


async def test_add_is_atomic_under_concurrent_calls(tmp_path):
    store = _store(tmp_path)
    results = await asyncio.gather(*(store.add("lock", "winner") for _ in range(20)))
    assert results.count(True) == 1
    assert results.count(False) == 19


async def test_flush_removes_every_cached_file(tmp_path):
    store = _store(tmp_path)
    await store.put("a", 1)
    await store.put("b", 2)
    await store.flush()
    assert await store.get("a") is None
    assert await store.get("b") is None
    assert not any(p.is_file() for p in tmp_path.iterdir())


async def test_directory_is_created_lazily_on_first_write(tmp_path):
    nested = tmp_path / "framework" / "cache"
    store = CacheStore(FileDriver(nested), "test_")
    assert not nested.exists()
    await store.put("k", "v")
    assert nested.is_dir()
