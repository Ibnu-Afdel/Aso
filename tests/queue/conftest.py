"""Process-global queue state isolation for `tests/queue/` (T-42), plus a DB fixture for tests
that exercise `handle()`'s database scope or the `failed_jobs` table.

Follows the `tests/database/conftest.py` test-binding pattern: one connection + one outer
transaction per test, rolled back at the end, so `failed_jobs` rows and `DB.scope()` effects never
leak between tests or into a real database file.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aso.database.engine import configure, install_sqlite_recipe
from aso.database.scope import open_scope, reset_test_binding, set_test_binding


@pytest.fixture(autouse=True)
def _reset_queue_state():
    import _jobs

    from aso.queue.manager import reset_queue

    reset_queue()
    _jobs.reset()
    yield
    reset_queue()
    _jobs.reset()


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
