"""Shared fixtures for `tests/mail/` (T-41).

`tests/conftest.py` already resets `Mail`'s fake state and the `array` transport's log around
every test (process-global, D-028). This file adds the one-connection database fixture
`tests/queue/conftest.py` uses, for the `.queue()` + `after_commit` tests.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aso.database.engine import configure, install_sqlite_recipe
from aso.database.scope import open_scope, reset_test_binding, set_test_binding


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
