"""Fixtures for the `aso.database` test suite.

Follows the S-2 test-binding pattern (`spikes/s2/test_s2.py`): one connection + one outer
transaction per test, bound with `join_transaction_mode="create_savepoint"`, rolled back at the
end. DDL (`Model.metadata.create_all`) is run **on that same connection**, inside the same
transaction, so creating tables is undone by the rollback too -- no separate drop step needed and
no schema leaks between tests on a persistent database (PostgreSQL).

`tests/conftest.py` (parent, autouse) resets `Model.registry`/`Model.metadata` before and after
every test. Because of that, model classes for these tests must be defined **inside the test
function** (or a fixture the test calls), never at module level -- a module-level class would be
mapped once, then have its table ripped out of `Model.metadata` by the next test's reset while
the class object itself survives with stale mapper state.

Run against SQLite (default) or PostgreSQL:
    uv run pytest -q tests/database
    DB_URL=postgresql+asyncpg://postgres:secret@127.0.0.1:55432/aso uv run pytest -q tests/database
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aso.database.engine import configure, install_query_listener, install_sqlite_recipe
from aso.database.scope import open_scope, reset_test_binding, set_test_binding

DB_URL = os.environ.get("DB_URL", "sqlite+aiosqlite://")
IS_SQLITE = DB_URL.startswith("sqlite")
IS_POSTGRES = DB_URL.startswith("postgres")


@pytest.fixture(scope="session")
async def engine():
    kwargs: dict[str, Any] = {}
    if IS_SQLITE:
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    eng = create_async_engine(DB_URL, **kwargs)
    if IS_SQLITE:
        install_sqlite_recipe(eng, {"foreign_keys": True})
    if IS_POSTGRES:
        # Unlike SQLite's fresh in-memory database, PostgreSQL's schema outlives the test run. A
        # table left over from an earlier run (or from spikes/s2/prod_check.py, which writes for
        # real) makes every later `create_all()` in this suite a silent no-op -- `checkfirst=True`
        # sees the table "already exists" and skips it, leaving the stale, incompatible columns
        # in place and turning every `INSERT` into a confusing `column "created_at" does not
        # exist`. Reset to a clean schema once before the session starts.
        from sqlalchemy import text

        async with eng.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    install_query_listener(eng)
    configure(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine):
    """Yields the bound `AsyncConnection`. Define models, then
    `await db.run_sync(Model.metadata.create_all)` before querying.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        token = set_test_binding(conn)
        try:
            async with open_scope():
                yield conn
        finally:
            reset_test_binding(token)
            await trans.rollback()


class FakeRequest:
    """Just enough of a Starlette `Request` for the pagination/query-string code (T-34)."""

    def __init__(self, path: str = "/posts", query: dict[str, str] | None = None) -> None:
        self.url = SimpleNamespace(path=path)
        self.query_params = query or {}


@pytest.fixture
def request_context():
    """Enter a fake request context so pagination can read `?page=` and build URLs.

    Returns a callable `use(path, query)` that (re-)enters the context; call it again in the same
    test to change the simulated request.

    No explicit teardown: `enter()` sets a `contextvars.ContextVar`, and a `Token` can only be
    `.reset()` from the exact `Context` it was produced in. pytest-asyncio runs the test body and
    this (sync) fixture's setup/teardown as separate `asyncio.Task`s -- different `Context`
    objects -- so stashing the token here and resetting it in teardown raises `ValueError: ...
    was created in a different Context`. It is also unnecessary: every test coroutine gets a
    fresh `Context` copied from pytest's stable outer (sync) context, so a `set()` made inside
    one test's task never leaks into another test's task regardless of cleanup.
    """
    from aso.context import RequestContext as _RequestContext
    from aso.context import enter

    def _use(path: str = "/posts", query: dict[str, str] | None = None) -> FakeRequest:
        request = FakeRequest(path, query)
        enter(_RequestContext(scope={}, request=request))
        return request

    return _use
