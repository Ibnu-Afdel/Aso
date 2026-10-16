"""`file` cache driver (T-44): one file per key under `storage/framework/cache/`.

The filename is the SHA-256 hash of the (already-prefixed) key, holding `{"expires_at": ...,
"value": ...}` as JSON. Writes are atomic (write to a temp file, then `os.replace`).
`increment()`/`decrement()` take an exclusive OS file lock (`fcntl.flock`), so several worker
processes on one machine still count correctly.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


class FileDriver:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    # ------------------------------------------------------------ paths

    def _file_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.directory / digest

    # ------------------------------------------------------------ reads

    async def get_raw(self, key: str) -> str | None:
        import anyio

        return await anyio.to_thread.run_sync(self._read, key)

    def _read(self, key: str) -> str | None:
        path = self._file_for(key)
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        expires_at = payload.get("expires_at")
        if expires_at is not None and expires_at <= time.time():
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            return None
        value = payload.get("value")
        return str(value) if value is not None else None

    # ------------------------------------------------------------ writes

    async def put_raw(self, key: str, raw: str, ttl: int | None) -> None:
        import anyio

        await anyio.to_thread.run_sync(self._write, key, raw, ttl)

    def _write(self, key: str, raw: str, ttl: int | None) -> None:
        expires_at = time.time() + ttl if ttl is not None else None
        self._write_payload(self._file_for(key), {"expires_at": expires_at, "value": raw})

    def _write_payload(self, path: Path, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.directory, prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload))
            os.replace(tmp_name, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    async def add_raw(self, key: str, raw: str, ttl: int | None) -> bool:
        import anyio

        return await anyio.to_thread.run_sync(self._add, key, raw, ttl)

    def _add(self, key: str, raw: str, ttl: int | None) -> bool:
        """Set `key` only if absent/expired, under the same `flock` used by `_increment` so two
        processes racing to add the same key never both "win" (T-44)."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._file_for(key)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with open(lock_path, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        existing = json.load(fh)
                    expires_at = existing.get("expires_at")
                    if expires_at is None or expires_at > time.time():
                        return False  # still present and not expired
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                new_expires_at = time.time() + ttl if ttl is not None else None
                self._write_payload(path, {"expires_at": new_expires_at, "value": raw})
                return True
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    async def forget(self, key: str) -> bool:
        import anyio

        return await anyio.to_thread.run_sync(self._forget, key)

    def _forget(self, key: str) -> bool:
        try:
            self._file_for(key).unlink()
            return True
        except FileNotFoundError:
            return False

    # ------------------------------------------------------------ atomic increment/decrement

    async def increment_raw(self, key: str, amount: int) -> int:
        import anyio

        return await anyio.to_thread.run_sync(self._increment, key, amount)

    def _increment(self, key: str, amount: int) -> int:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._file_for(key)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with open(lock_path, "w") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                existing_value: str | None = None
                expires_at: float | None = None
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        existing = json.load(fh)
                    expires_at = existing.get("expires_at")
                    if expires_at is not None and expires_at <= time.time():
                        expires_at = None
                    else:
                        existing_value = existing.get("value")
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                current = int(existing_value) if existing_value is not None else 0
                new_value = current + amount
                self._write_payload(path, {"expires_at": expires_at, "value": str(new_value)})
                return new_value
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    # ------------------------------------------------------------ flush (tests)

    async def flush(self, prefix: str = "") -> None:
        import anyio

        await anyio.to_thread.run_sync(self._flush)

    def _flush(self) -> None:
        if not self.directory.exists():
            return
        for child in self.directory.iterdir():
            if child.is_file():
                with contextlib.suppress(OSError):
                    child.unlink()
