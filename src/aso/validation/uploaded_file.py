"""`UploadedFile`: a framework-neutral wrapper around an uploaded file (T-19, T-43).

Built from Starlette's `UploadFile` during input collection (`form_request.collect_input`).
`store()`/`store_as()` persist through `aso.storage` (T-43).
"""

from __future__ import annotations

import mimetypes
import secrets
import string
from pathlib import PurePosixPath
from typing import Any

_NAME_ALPHABET = string.ascii_letters + string.digits


def _random_name(length: int = 40) -> str:
    """40 random characters (Laravel's `Str::random(40)` / `hashName()`), never the original name."""
    return "".join(secrets.choice(_NAME_ALPHABET) for _ in range(length))


class UploadedFile:
    """One uploaded file. `filename`/`content_type`/`size` mirror Laravel's `UploadedFile`."""

    def __init__(self, filename: str, content_type: str | None, data: bytes) -> None:
        self.filename = filename or ""
        self.content_type = content_type or mimetypes.guess_type(filename or "")[0]
        self._data = data

    @property
    def size(self) -> int:
        """Size in bytes (callers divide by 1024 for Laravel's kilobyte-based `max:`)."""
        return len(self._data)

    def extension(self) -> str:
        suffix = PurePosixPath(self.filename).suffix
        return suffix[1:].lower() if suffix else ""

    async def read(self) -> bytes:
        return self._data

    async def store(self, directory: str, *, disk: str | None = None) -> str:
        """Store under a generated name: 40 random characters + the extension (T-43)."""
        return await self._store(directory, f"{_random_name()}{self._suffix()}", disk)

    async def store_as(self, directory: str, name: str, *, disk: str | None = None) -> str:
        """Store under an explicit name (T-43)."""
        return await self._store(directory, name, disk)

    def _suffix(self) -> str:
        suffix = PurePosixPath(self.filename).suffix
        return suffix if suffix else ""

    async def _store(self, directory: str, name: str, disk: str | None) -> str:
        from aso.storage import storage

        path = f"{directory.strip('/')}/{name}"
        await storage(disk).put(path, await self.read())
        return path

    @classmethod
    def from_upload_file(cls, upload: Any, data: bytes) -> UploadedFile:
        """Build an `UploadedFile` from a Starlette `UploadFile` plus its already-read bytes."""
        return cls(getattr(upload, "filename", "") or "", getattr(upload, "content_type", None), data)

    @classmethod
    def fake(cls) -> _FakeUploadedFileFactory:
        """`UploadedFile.fake().image(...)` / `.create(...)` for tests (T-56)."""
        return _FakeUploadedFileFactory()


class _FakeUploadedFileFactory:
    """Factory returned by `UploadedFile.fake()`. Mirrors Laravel's `UploadedFile::fake()`."""

    def image(self, name: str = "photo.jpg", width: int = 10, height: int = 10) -> UploadedFile:
        # Not a real decodable image: good enough for size/mime-based rules and storage tests.
        payload = b"\xff\xd8\xff\xe0" + bytes([max(width, 1) % 256, max(height, 1) % 256]) * 8
        return UploadedFile(name, mimetypes.guess_type(name)[0] or "image/jpeg", payload)

    def create(self, name: str = "file.txt", size_kb: int = 0, mime_type: str | None = None) -> UploadedFile:
        return UploadedFile(name, mime_type, b"0" * (size_kb * 1024))
