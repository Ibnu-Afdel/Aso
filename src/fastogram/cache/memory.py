"""`memory` cache driver (T-44): a process-local dict with monotonic-clock expiry.

Each Uvicorn worker has its own, so counters and rate limits are per worker. Use it for tests
and single-process development only (the T-44 page is explicit about this).
"""

from __future__ import annotations

import time


class MemoryDriver:
    """`{key: (expires_at_monotonic_or_None, raw_json_str)}`, kept for the life of the process."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float | None, str]] = {}

    async def get_raw(self, key: str) -> str | None:
        return self._read(key)

    def _read(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires_at, raw = entry
        if expires_at is not None and expires_at <= time.monotonic():
            self._data.pop(key, None)
            return None
        return raw

    async def put_raw(self, key: str, raw: str, ttl: int | None) -> None:
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._data[key] = (expires_at, raw)

    async def add_raw(self, key: str, raw: str, ttl: int | None) -> bool:
        """Set `key` only if absent/expired. Atomic: nothing awaits between the check and the
        write, so no other coroutine on this event loop can interleave (T-44)."""
        if self._read(key) is not None:
            return False
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._data[key] = (expires_at, raw)
        return True

    async def forget(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    async def increment_raw(self, key: str, amount: int) -> int:
        current_raw = self._read(key)  # also prunes an expired entry
        current = int(current_raw) if current_raw is not None else 0
        entry = self._data.get(key)
        expires_at = entry[0] if entry is not None else None
        new_value = current + amount
        self._data[key] = (expires_at, str(new_value))
        return new_value

    async def flush(self, prefix: str = "") -> None:
        self._data.clear()
