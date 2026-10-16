"""`storage(disk)` / `storage()` (T-43): the local filesystem disk adapter.

Disks are configured in `config/filesystems.py`; sensible `local`/`public` defaults apply when
that file is missing (`_disk_spec`). All I/O runs in a worker thread (`anyio.to_thread`) so a
large file never blocks the event loop.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from aso.config import config, env

_fakes: dict[str, Path] = {}
_fake_tempdirs: dict[str, Any] = {}


def storage(disk: str | None = None) -> Disk:
    """The named disk, or the configured default (`config/filesystems.py` -> `default`)."""
    name = disk or _default_disk_name()
    spec = _disk_spec(name)
    root = _fakes.get(name) or Path(spec["root"])
    return Disk(name, root, spec.get("url"))


def _default_disk_name() -> str:
    return config("filesystems.default") or "local"


def _disk_spec(name: str) -> dict[str, Any]:
    disks = config("filesystems.disks")
    if isinstance(disks, dict) and name in disks:
        return disks[name]
    from aso.foundation.paths import base_path

    defaults: dict[str, dict[str, Any]] = {
        "local": {"driver": "local", "root": str(base_path("storage", "app"))},
        "public": {
            "driver": "local",
            "root": str(base_path("storage", "app", "public")),
            "url": env("APP_URL", "http://localhost:8000").rstrip("/") + "/storage",
        },
    }
    if name in defaults:
        return defaults[name]
    raise RuntimeError(f'Filesystem disk "{name}" is not configured. Add it to config/filesystems.py `disks`.')


class Disk:
    """One configured disk. Async `put`/`get`/`exists`/`delete`; sync `url` (no I/O, T-43)."""

    def __init__(self, name: str, root: Path, url_prefix: str | None) -> None:
        self.name = name
        self.root = Path(root)
        self._url_prefix = url_prefix

    def _resolve(self, relative: str) -> Path:
        return self.root / _safe_relative(relative)

    def url(self, relative: str) -> str:
        if not self._url_prefix:
            raise RuntimeError(f'Disk "{self.name}" has no `url` configured in config/filesystems.py.')
        return f"{self._url_prefix.rstrip('/')}/{_safe_relative(relative).as_posix()}"

    async def put(self, relative: str, data: bytes | str) -> None:
        import anyio

        target = self._resolve(relative)
        payload = data.encode() if isinstance(data, str) else data
        await anyio.to_thread.run_sync(_write_atomic, target, payload)

    async def get(self, relative: str) -> bytes:
        import anyio

        return await anyio.to_thread.run_sync(self._resolve(relative).read_bytes)

    async def exists(self, relative: str) -> bool:
        import anyio

        return await anyio.to_thread.run_sync(self._resolve(relative).exists)

    async def delete(self, relative: str) -> bool:
        import anyio

        return await anyio.to_thread.run_sync(_delete, self._resolve(relative))


def _safe_relative(relative: str) -> PurePosixPath:
    """Reject `..` and absolute paths (Laravel/`UploadedFile.store()` never trust path input)."""
    path = PurePosixPath(str(relative))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Invalid storage path: {relative!r}")
    return path


def _write_atomic(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp_name, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def _delete(target: Path) -> bool:
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------- testing: storage.fake(disk)


def fake(disk: str = "local") -> Path:
    """`storage.fake("public")`: swap `disk`'s root for an empty temp dir (Laravel's
    `Storage::fake()`). Stays swapped until `reset_fakes()` runs."""
    tmp = tempfile.TemporaryDirectory(prefix=f"aso-storage-{disk}-")
    _fake_tempdirs[disk] = tmp
    _fakes[disk] = Path(tmp.name)
    return Path(tmp.name)


def reset_fakes() -> None:
    """Undo every `storage.fake()` swap. Call between tests (not wired into a test runner yet --
    see the T-43/T-56 note in this package's final report)."""
    for tmp in _fake_tempdirs.values():
        tmp.cleanup()
    _fake_tempdirs.clear()
    _fakes.clear()


storage.fake = fake  # type: ignore[attr-defined]
storage.reset_fakes = reset_fakes  # type: ignore[attr-defined]


# ---------------------------------------------------------------- storage:link


def link_public_storage() -> Path:
    """Create a **relative** symlink `public/storage` -> the `public` disk's root (T-43, resolved
    2026-10-09: relative so it survives moving the project or mounting it in a container).

    Plain function; the CLI's `storage:link` command (T-50) calls it.
    """
    from aso.foundation.paths import base_path

    target = Path(_disk_spec("public")["root"])
    link = base_path("public", "storage")
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            raise RuntimeError(f"{link} already exists and is a real directory, not a symlink. Remove it first.")
        link.unlink()
    target.mkdir(parents=True, exist_ok=True)
    relative_target = os.path.relpath(target, link.parent)
    link.symlink_to(relative_target, target_is_directory=True)
    return link
