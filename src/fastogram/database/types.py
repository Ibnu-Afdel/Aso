"""Column types completing T-31: `UtcDateTime`, `Encrypted`, `Hashed`, and a pure-Python UUIDv7.

`UtcDateTime` always returns aware UTC datetimes, even from SQLite/MySQL which drop the zone.
`Encrypted`/`Hashed` lazily import `fastogram.security` (built by another agent) so this package
does not hard-depend on it; a clear error is raised if it is missing.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, event
from sqlalchemy.orm import Mapper
from sqlalchemy.types import TypeDecorator

__all__ = ["Encrypted", "Hashed", "UtcDateTime", "uuid7", "ulid"]


class UtcDateTime(TypeDecorator):
    """`DateTime(timezone=True)` that always round-trips as aware UTC (T-31).

    SQLite and MySQL `DATETIME` columns store no timezone, so a naive value comes back from
    those backends. This type converts aware input to UTC before binding (rejecting naive input)
    and reattaches `tzinfo=UTC` on the way out when the driver returned a naive value.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"UtcDateTime received a naive datetime ({value!r}); pass an aware datetime.")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7 (ordered, index-friendly). Uses `uuid.uuid7()` on Python 3.14+."""
    native = getattr(uuid, "uuid7", None)
    if native is not None:
        return native()
    # Minimal RFC 9562 version 7: 48-bit ms timestamp + random bits, version/variant set.
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms << 80) | rand
    value &= ~(0xF << 76)
    value |= 0x7 << 76  # version 7
    value &= ~(0x3 << 62)
    value |= 0x2 << 62  # variant 10
    return uuid.UUID(int=value)


_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """26-character ULID: 48-bit ms timestamp + 80 random bits, base32 (Crockford) encoded."""
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms << 80) | rand
    chars = []
    for _ in range(26):
        chars.append(_ULID_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def _security() -> Any:
    try:
        from fastogram import security
    except ImportError as exc:  # pragma: no cover - exercised only when security is missing
        raise RuntimeError(
            "Encrypted/Hashed columns need `fastogram.security` (crypt/hash). Is that package built?"
        ) from exc
    return security


class Encrypted(TypeDecorator):
    """`Mapped[str] = mapped_column(Encrypted(String))` — encrypted at rest with `APP_KEY` (T-40)."""

    impl = String  # class-level fallback TypeDecorator.__init__ requires; __init__ overrides it below.
    cache_ok = True

    def __init__(self, impl: Any = String, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.impl = impl() if isinstance(impl, type) else impl

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return _security().crypt.encrypt(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return _security().crypt.decrypt(value)


def _hash_if_needed(value: Any) -> Any:
    """Laravel's `hashed` cast: hash a plain value, pass an already-hashed one through unchanged."""
    if value is None:
        return None
    security = _security()
    is_hashed = getattr(security.hash, "is_hashed", None)
    already_hashed = is_hashed(value) if callable(is_hashed) else bool(value) and str(value).startswith("$")
    if already_hashed:
        return value
    return security.hash.make(value)


def _hash_on_set(target: Any, value: Any, oldvalue: Any, initiator: Any) -> Any:
    return _hash_if_needed(value)


@event.listens_for(Mapper, "mapper_configured")
def _wire_hashed_columns(mapper: Any, class_: Any) -> None:
    """Hash `Hashed` columns on assignment, not just at the SQL boundary (T-40's `hashed` cast).

    `mapper_configured` fires before a mapped class's own `__init__` runs its `setattr()` calls
    (declarative's generated constructor), so both `Model(password=...)` and later
    `instance.password = ...` go through `_hash_on_set` -- `user.password` is never plaintext in
    memory after `create()`. `process_bind_param` below stays as a second line of defense for any
    value that reaches the database without going through the instrumented attribute (e.g. a Core
    statement).
    """
    for prop in mapper.column_attrs:
        columns = getattr(prop, "columns", None)
        if not columns or not isinstance(columns[0].type, Hashed):
            continue
        attr = getattr(class_, prop.key)
        if not event.contains(attr, "set", _hash_on_set):
            event.listen(attr, "set", _hash_on_set, retval=True)


class Hashed(TypeDecorator):
    """`Mapped[str] = mapped_column(Hashed())` — hashes on assignment unless already hashed (T-40).

    See `_wire_hashed_columns` for the assignment-time hook; `process_bind_param` is a fallback.
    """

    impl = String
    cache_ok = True

    def __init__(self, impl: Any = String, *args: Any, **kwargs: Any) -> None:
        # `Hashed(String(255))` (the T-38 example) must keep the length, not nest String in String.
        super().__init__(*args, **kwargs)
        self.impl = impl() if isinstance(impl, type) else impl

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return _hash_if_needed(value)
