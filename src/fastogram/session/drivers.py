"""Session storage drivers (T-18): `array`, `database`, `cookie`.

`array` and `database` are id-based: the browser's cookie carries a *signed* session id
(`sign_id`/`unsign_id`), and the payload lives server-side. `cookie` has no server-side store at
all -- the browser's cookie *is* the (encrypted) payload, id and all.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from typing import Any

from itsdangerous import BadSignature, Signer

from fastogram.exceptions.types import SessionTooLarge
from fastogram.security.keys import app_key, fernet_key, previous_app_keys

SESSION_ID_PURPOSE = b"fastogram-session-id"
COOKIE_PAYLOAD_PURPOSE = b"fastogram-session"
COOKIE_PAYLOAD_LIMIT = 4000


@dataclass
class SessionRecord:
    id: str
    data: dict[str, Any]
    last_activity: int


# ---------------------------------------------------------------- signed session id (array, database)


def _signer() -> Signer:
    from fastogram.security.keys import derive_key

    key = derive_key(app_key(), SESSION_ID_PURPOSE)
    return Signer(key)


def sign_id(raw_id: str) -> str:
    return _signer().sign(raw_id.encode()).decode()


def unsign_id(value: str | None) -> str | None:
    """The raw id, or `None` on a missing/bad signature (never raises -- a new session starts)."""
    if not value:
        return None
    try:
        return _signer().unsign(value.encode()).decode()
    except BadSignature:
        return None


# ---------------------------------------------------------------- array driver


class ArrayDriver:
    """In-process dict, kept between requests until the process ends (tests, D-006)."""

    def __init__(self) -> None:
        self._store: dict[str, SessionRecord] = {}

    async def load(self, sid: str, _lifetime_seconds: int) -> SessionRecord | None:
        record = self._store.get(sid)
        if record is None:
            return None
        return SessionRecord(record.id, copy.deepcopy(record.data), record.last_activity)

    async def save(self, record: SessionRecord, **_meta: Any) -> None:
        self._store[record.id] = SessionRecord(record.id, copy.deepcopy(record.data), record.last_activity)

    async def delete(self, sid: str) -> None:
        self._store.pop(sid, None)

    async def prune(self, lifetime_seconds: int) -> int:
        cutoff = time.time() - lifetime_seconds
        expired = [sid for sid, record in self._store.items() if record.last_activity < cutoff]
        for sid in expired:
            del self._store[sid]
        return len(expired)

    def clear(self) -> None:
        self._store.clear()


_array = ArrayDriver()


def array_driver() -> ArrayDriver:
    return _array


def clear_array_store() -> None:
    """Empty the `array` driver's in-memory store (used by the test plugin between tests)."""
    _array.clear()


# ---------------------------------------------------------------- database driver


class DatabaseDriver:
    """The `sessions` table, via the engine's own short connection (never the request's `AsyncSession`)."""

    def __init__(self, table: str = "sessions") -> None:
        self.table = table

    async def load(self, sid: str, lifetime_seconds: int) -> SessionRecord | None:
        from sqlalchemy import text

        from fastogram.database.engine import engine

        cutoff = int(time.time()) - lifetime_seconds
        async with engine().begin() as conn:
            result = await conn.execute(
                text(f"SELECT payload, last_activity FROM {self.table} WHERE id = :id AND last_activity >= :cutoff"),
                {"id": sid, "cutoff": cutoff},
            )
            row = result.first()
        if row is None:
            return None
        payload = row[0]
        data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        return SessionRecord(sid, data, int(row[1]))

    async def save(
        self,
        record: SessionRecord,
        *,
        user_id: Any = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        from sqlalchemy import text

        from fastogram.database.engine import engine

        payload = json.dumps(record.data)
        params = {
            "id": record.id,
            "payload": payload,
            "last_activity": record.last_activity,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        async with engine().begin() as conn:
            result = await conn.execute(
                text(
                    f"UPDATE {self.table} SET payload = :payload, last_activity = :last_activity, "
                    "user_id = :user_id, ip_address = :ip_address, user_agent = :user_agent WHERE id = :id"
                ),
                params,
            )
            if result.rowcount == 0:
                await conn.execute(
                    text(
                        f"INSERT INTO {self.table} (id, user_id, ip_address, user_agent, payload, last_activity) "
                        "VALUES (:id, :user_id, :ip_address, :user_agent, :payload, :last_activity)"
                    ),
                    params,
                )

    async def delete(self, sid: str) -> None:
        from sqlalchemy import text

        from fastogram.database.engine import engine

        async with engine().begin() as conn:
            await conn.execute(text(f"DELETE FROM {self.table} WHERE id = :id"), {"id": sid})

    async def prune(self, lifetime_seconds: int) -> int:
        from sqlalchemy import text

        from fastogram.database.engine import engine

        cutoff = int(time.time()) - lifetime_seconds
        async with engine().begin() as conn:
            result = await conn.execute(text(f"DELETE FROM {self.table} WHERE last_activity < :cutoff"), {"cutoff": cutoff})
        return int(result.rowcount or 0)


# ---------------------------------------------------------------- cookie driver (whole payload, encrypted)


def _cookie_fernet():
    from cryptography.fernet import Fernet, MultiFernet

    keys = [app_key(), *previous_app_keys()]
    return MultiFernet([Fernet(fernet_key(k, COOKIE_PAYLOAD_PURPOSE)) for k in keys])


def encode_cookie_payload(record: SessionRecord) -> str:
    """Encrypt the whole session into one cookie value. Raises `SessionTooLarge` above 4000 bytes."""
    payload = json.dumps({"id": record.id, "data": record.data, "last_activity": record.last_activity}).encode()
    token = _cookie_fernet().encrypt(payload)
    if len(token) > COOKIE_PAYLOAD_LIMIT:
        raise SessionTooLarge(
            f"The session payload is {len(token)} bytes, over the {COOKIE_PAYLOAD_LIMIT} byte "
            "cookie-driver limit. Switch SESSION_DRIVER to database, or store less in the session."
        )
    return token.decode()


def decode_cookie_payload(raw: str | None) -> SessionRecord | None:
    """Decrypt the cookie, or `None` on a missing/tampered/expired value (never raises)."""
    if not raw:
        return None
    try:
        payload = _cookie_fernet().decrypt(raw.encode())
    except Exception:
        return None
    try:
        obj = json.loads(payload)
        return SessionRecord(obj["id"], obj["data"], obj["last_activity"])
    except Exception:
        return None


# ---------------------------------------------------------------- dispatch + pruning


def _server_driver(name: str, table: str) -> ArrayDriver | DatabaseDriver:
    if name == "database":
        return DatabaseDriver(table)
    return array_driver()


async def prune_sessions(table: str | None = None) -> int:
    """Delete expired rows/entries now (the `session:prune` command; also run by the lottery)."""
    from fastogram.session.configuration import settings

    cfg = settings()
    driver = _server_driver(cfg.driver, table or cfg.table)
    if not hasattr(driver, "prune"):
        return 0
    return await driver.prune(cfg.lifetime * 60)
