"""Fixtures for `tests/factories/` (T-36): the same test-binding pattern as
`tests/database/conftest.py` (one connection + one outer transaction per test, rolled back at the
end), plus a helper that boots a tiny fixture app for the `factory_for()`/`has_<relation>`
convention lookups, which need real files on disk under `app/models/` and
`database/factories/`."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastogram.database.engine import configure, install_sqlite_recipe
from fastogram.database.scope import open_scope, reset_test_binding, set_test_binding

FACTORIES_APP = Path(__file__).parent.parent / "fixtures" / "factories_app"

DB_URL = os.environ.get("DB_URL", "sqlite+aiosqlite://")
IS_SQLITE = DB_URL.startswith("sqlite")


@pytest.fixture
async def engine():
    kwargs: dict[str, Any] = {}
    if IS_SQLITE:
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    eng = create_async_engine(DB_URL, **kwargs)
    if IS_SQLITE:
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


@pytest.fixture
def factories_app(db):
    """Puts `tests/fixtures/factories_app` on `sys.path` and imports its `User`/`Post` models and
    `UserFactory`/`PostFactory`, for the convention-based lookup tests. Shares the rolled-back
    `db` connection above, so anything created is undone at the end of the test."""
    root = str(FACTORIES_APP)
    inserted = root not in sys.path
    if inserted:
        sys.path.insert(0, root)
    try:
        import app.models.post as post_module
        import app.models.user as user_module

        yield user_module.User, post_module.Post
    finally:
        if inserted:
            sys.path.remove(root)
