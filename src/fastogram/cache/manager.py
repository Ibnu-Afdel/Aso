"""`cache()` / `cache(store)` (T-44): resolve the configured store, wrap its driver.

Every value is serialised with the framework's JSON encoder (the same one used for Inertia
props, T-16) and never with `pickle` -- a shared Redis that could feed pickled data back to the
app would be a remote-code-execution risk. A value that is not JSON-serialisable raises at once.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastogram.config import config, env

_memory_registry: dict[str, Any] = {}
_redis_registry: dict[str, Any] = {}


def cache(store: str | None = None) -> CacheStore:
    """The named store, or the configured default (`config/cache.py` -> `default`)."""
    name = store or _default_store_name()
    driver = _driver_for(name)
    prefix = config("cache.prefix", "fastogram_cache_")
    return CacheStore(driver, prefix)


def _default_store_name() -> str:
    configured = config("cache.default")
    if configured:
        return configured
    from fastogram.foundation.application import environment

    # No config/cache.py in the app: memory in tests (matches the page's `.env.testing` default),
    # file otherwise (the page's own `config/cache.py` default).
    return "memory" if environment("testing") else "file"


def _store_spec(name: str) -> dict[str, Any]:
    stores = config("cache.stores")
    if isinstance(stores, dict) and name in stores:
        return stores[name]
    from fastogram.foundation.paths import storage_path

    defaults: dict[str, dict[str, Any]] = {
        "memory": {"driver": "memory"},
        "file": {"driver": "file", "path": str(storage_path("framework", "cache"))},
        "redis": {"driver": "redis", "connection": env("REDIS_URL", "redis://127.0.0.1:6379/1")},
    }
    if name in defaults:
        return defaults[name]
    raise RuntimeError(f'Cache store "{name}" is not configured. Add it to config/cache.py `stores`.')


def _driver_for(name: str) -> Any:
    spec = _store_spec(name)
    driver_type = spec.get("driver", name)
    if driver_type == "memory":
        if name not in _memory_registry:
            from fastogram.cache.memory import MemoryDriver

            _memory_registry[name] = MemoryDriver()
        return _memory_registry[name]
    if driver_type == "file":
        from fastogram.cache.file import FileDriver

        path = spec.get("path") or spec.get("root")
        if not path:
            raise RuntimeError(f'Cache store "{name}" uses the "file" driver but has no `path`.')
        return FileDriver(Path(path))
    if driver_type == "redis":
        if name not in _redis_registry:
            from fastogram.cache.redis_store import RedisDriver

            url = spec.get("connection") or spec.get("url") or env("REDIS_URL", "redis://127.0.0.1:6379/1")
            _redis_registry[name] = RedisDriver(url)
        return _redis_registry[name]
    raise RuntimeError(f'Unknown cache driver "{driver_type}" for store "{name}".')


class CacheStore:
    """One resolved store. `get`/`put`/`remember`/`forget`/`increment`/`decrement`, plus `flush`
    for tests."""

    def __init__(self, driver: Any, prefix: str) -> None:
        self._driver = driver
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        raw = await self._driver.get_raw(self._key(key))
        if raw is None:
            return default
        return json.loads(raw)

    async def put(self, key: str, value: Any, ttl: int | timedelta | None = None) -> None:
        raw = _encode(value)
        await self._driver.put_raw(self._key(key), raw, _ttl_seconds(ttl))

    async def add(self, key: str, value: Any, ttl: int | timedelta | None = None) -> bool:
        """Atomically set `key` only if it is not already present (or has expired), returning
        whether it was set (Laravel's `Cache::add()`). Unlike a `get()`-then-`put()` pair, each
        driver's `add_raw` is check-and-set in one step, so this is safe for mutual exclusion
        (the scheduler's `without_overlapping` lock, T-45)."""
        raw = _encode(value)
        return await self._driver.add_raw(self._key(key), raw, _ttl_seconds(ttl))

    async def forget(self, key: str) -> bool:
        return await self._driver.forget(self._key(key))

    async def increment(self, key: str, amount: int = 1) -> int:
        return await self._driver.increment_raw(self._key(key), amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        return await self._driver.increment_raw(self._key(key), -amount)

    async def remember(
        self,
        key: str,
        ttl: int | timedelta | None,
        callback: Callable[[], Any] | Callable[[], Awaitable[Any]],
    ) -> Any:
        """Return the cached value, or run `callback` (sync or async), cache it, and return it."""
        raw = await self._driver.get_raw(self._key(key))
        if raw is not None:
            return json.loads(raw)
        value = callback()
        if inspect.isawaitable(value):
            value = await value
        await self.put(key, value, ttl)
        return value

    async def flush(self) -> None:
        """Clear this store's keys. Test helper -- not part of the T-44 Laravel-facing API."""
        await self._driver.flush(self._prefix)


def _ttl_seconds(ttl: int | timedelta | None) -> int | None:
    if ttl is None:
        return None
    if isinstance(ttl, timedelta):
        return int(ttl.total_seconds())
    return int(ttl)


def _encode(value: Any) -> str:
    from fastogram.inertia.json_encode import to_jsonable

    try:
        return json.dumps(to_jsonable(value), separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise TypeError(f"Cache values must be JSON-serialisable (got {type(value).__name__}): {exc}") from exc


def flush_all() -> None:
    """Drop every driver this process has built so far (memory dicts, Redis clients).

    Process-scoped test isolation: call it between tests so one test's keys/limiters never leak
    into the next. Laravel has no equivalent (`Cache::flush()` there is store-scoped, not
    process-scoped); this exists because `memory`/`redis` driver instances are cached per store
    name for the life of the process (T-44: "memory: a process-local dict").
    """
    _memory_registry.clear()
    _redis_registry.clear()
