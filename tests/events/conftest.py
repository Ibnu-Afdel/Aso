"""Shared fixtures for `tests/events/` (T-46).

`tests/conftest.py` already resets `Event`'s fake state and listener registry around every test
(process-global, D-027). This file adds: clearing `_fixtures.calls`, and the same one-connection
database fixture `tests/queue/conftest.py` uses, for tests that dispatch a queued listener inside
`DB.transaction()`.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastogram.database.engine import configure, install_sqlite_recipe
from fastogram.database.scope import open_scope, reset_test_binding, set_test_binding


@pytest.fixture(autouse=True)
def _reset_event_fixtures():
    import _event_fixtures as _fixtures

    _fixtures.reset()
    yield
    _fixtures.reset()


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    install_sqlite_recipe(eng, {"foreign_keys": True})
    configure(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        token = set_test_binding(conn)
        try:
            async with open_scope():
                yield conn
        finally:
            reset_test_binding(token)
            await trans.rollback()
