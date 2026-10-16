"""Driver-level tests (T-18): `array`, `database`, `cookie`, and the signed/encrypted cookie values.

Database tests use `aso.database.engine.make_engine` against SQLite (in-memory for the
default run, or `DB_URL` for PostgreSQL -- see `BUILD.md`), creating the `sessions` table
ourselves since the skeleton migration that normally does this is not part of this package.
"""

from __future__ import annotations

import os
import time

import pytest
from sqlalchemy import text

from aso.database import engine as engine_module
from aso.exceptions.types import SessionTooLarge
from aso.security.keys import generate_key
from aso.session.drivers import (
    DatabaseDriver,
    SessionRecord,
    array_driver,
    clear_array_store,
    decode_cookie_payload,
    encode_cookie_payload,
    sign_id,
    unsign_id,
)


@pytest.fixture(autouse=True)
def _app_key(monkeypatch):
    key = generate_key()
    monkeypatch.setattr("aso.config.config", lambda k, default=None: key if k == "app.key" else default)
    monkeypatch.delenv("APP_PREVIOUS_KEYS", raising=False)
    yield key


# ------------------------------------------------------------ signed session id


def test_sign_and_unsign_roundtrip() -> None:
    signed = sign_id("abc123")
    assert unsign_id(signed) == "abc123"


def test_tampered_signature_yields_none_not_an_error() -> None:
    signed = sign_id("abc123")
    # flip a middle character: the last base64 character may only carry padding bits
    i = len(signed) - 5
    tampered = signed[:i] + ("a" if signed[i] != "a" else "b") + signed[i + 1 :]
    assert unsign_id(tampered) is None


def test_unsign_missing_value_is_none() -> None:
    assert unsign_id(None) is None
    assert unsign_id("") is None


def test_different_app_key_cannot_unsign(monkeypatch) -> None:
    signed = sign_id("abc123")
    other_key = generate_key()
    monkeypatch.setattr("aso.config.config", lambda k, default=None: other_key if k == "app.key" else default)
    assert unsign_id(signed) is None


# ------------------------------------------------------------ array driver


async def test_array_driver_save_then_load() -> None:
    clear_array_store()
    driver = array_driver()
    record = SessionRecord("sid-1", {"a": 1}, int(time.time()))
    await driver.save(record)
    loaded = await driver.load("sid-1", 120 * 60)
    assert loaded is not None
    assert loaded.data == {"a": 1}
    clear_array_store()


async def test_array_driver_missing_id_returns_none() -> None:
    clear_array_store()
    assert await array_driver().load("nope", 120 * 60) is None


async def test_array_driver_delete() -> None:
    clear_array_store()
    driver = array_driver()
    await driver.save(SessionRecord("sid-1", {}, int(time.time())))
    await driver.delete("sid-1")
    assert await driver.load("sid-1", 120 * 60) is None
    clear_array_store()


async def test_array_driver_load_returns_a_copy_not_a_live_reference() -> None:
    clear_array_store()
    driver = array_driver()
    data = {"items": [1, 2]}
    await driver.save(SessionRecord("sid-1", data, int(time.time())))
    loaded = await driver.load("sid-1", 120 * 60)
    loaded.data["items"].append(3)
    reloaded = await driver.load("sid-1", 120 * 60)
    assert reloaded.data["items"] == [1, 2]
    clear_array_store()


async def test_array_driver_prune_removes_expired_only() -> None:
    clear_array_store()
    driver = array_driver()
    await driver.save(SessionRecord("fresh", {}, int(time.time())))
    await driver.save(SessionRecord("stale", {}, int(time.time()) - 1000))
    removed = await driver.prune(lifetime_seconds=60)
    assert removed == 1
    assert await driver.load("fresh", 120 * 60) is not None
    assert await driver.load("stale", 120 * 60) is None
    clear_array_store()


async def test_array_driver_clears_between_tests() -> None:
    clear_array_store()
    await array_driver().save(SessionRecord("sid-x", {}, int(time.time())))
    clear_array_store()
    assert await array_driver().load("sid-x", 120 * 60) is None


# ------------------------------------------------------------ database driver


@pytest.fixture
async def db_engine():
    url = os.environ.get("DB_URL", "sqlite+aiosqlite://")
    engine = engine_module.make_engine(url)
    engine_module.configure(engine)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE sessions (id VARCHAR(255) PRIMARY KEY, user_id INTEGER, "
                "ip_address VARCHAR(45), user_agent TEXT, payload TEXT NOT NULL, last_activity INTEGER NOT NULL)"
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE sessions"))
    await engine.dispose()


async def test_database_driver_save_then_load(db_engine) -> None:
    driver = DatabaseDriver()
    now = int(time.time())
    await driver.save(SessionRecord("sid-1", {"a": 1}, now), user_id=7, ip_address="127.0.0.1", user_agent="pytest")
    loaded = await driver.load("sid-1", 120 * 60)
    assert loaded is not None
    assert loaded.data == {"a": 1}
    assert loaded.last_activity == now


async def test_database_driver_upserts_on_second_save(db_engine) -> None:
    driver = DatabaseDriver()
    now = int(time.time())
    await driver.save(SessionRecord("sid-1", {"a": 1}, now))
    await driver.save(SessionRecord("sid-1", {"a": 2}, now + 1))
    loaded = await driver.load("sid-1", 120 * 60)
    assert loaded.data == {"a": 2}
    async with db_engine.begin() as conn:
        result = await conn.execute(text("SELECT count(*) FROM sessions"))
        assert result.scalar() == 1


async def test_database_driver_ignores_expired_rows(db_engine) -> None:
    driver = DatabaseDriver()
    stale = int(time.time()) - 10_000
    await driver.save(SessionRecord("sid-1", {"a": 1}, stale))
    assert await driver.load("sid-1", lifetime_seconds=60) is None


async def test_database_driver_delete(db_engine) -> None:
    driver = DatabaseDriver()
    await driver.save(SessionRecord("sid-1", {}, int(time.time())))
    await driver.delete("sid-1")
    assert await driver.load("sid-1", 120 * 60) is None


async def test_database_driver_prune_deletes_expired_rows(db_engine) -> None:
    driver = DatabaseDriver()
    await driver.save(SessionRecord("fresh", {}, int(time.time())))
    await driver.save(SessionRecord("stale", {}, int(time.time()) - 10_000))
    removed = await driver.prune(lifetime_seconds=60)
    assert removed == 1
    assert await driver.load("fresh", 120 * 60) is not None


# ------------------------------------------------------------ cookie driver (encrypted payload)


def test_cookie_payload_roundtrip() -> None:
    record = SessionRecord("sid-1", {"a": 1}, int(time.time()))
    token = encode_cookie_payload(record)
    decoded = decode_cookie_payload(token)
    assert decoded is not None
    assert decoded.id == "sid-1"
    assert decoded.data == {"a": 1}


def test_cookie_payload_tampered_returns_none() -> None:
    record = SessionRecord("sid-1", {"a": 1}, int(time.time()))
    token = encode_cookie_payload(record)
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    assert decode_cookie_payload(tampered) is None


def test_cookie_payload_missing_is_none() -> None:
    assert decode_cookie_payload(None) is None
    assert decode_cookie_payload("") is None


def test_cookie_payload_over_4000_bytes_raises_session_too_large() -> None:
    record = SessionRecord("sid-1", {"blob": "x" * 5000}, int(time.time()))
    with pytest.raises(SessionTooLarge):
        encode_cookie_payload(record)


def test_cookie_payload_wrong_app_key_cannot_decrypt(monkeypatch) -> None:
    record = SessionRecord("sid-1", {"a": 1}, int(time.time()))
    token = encode_cookie_payload(record)
    other_key = generate_key()
    monkeypatch.setattr("aso.config.config", lambda k, default=None: other_key if k == "app.key" else default)
    assert decode_cookie_payload(token) is None
