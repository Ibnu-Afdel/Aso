"""Fixtures for `tests/testing/`'s feature tests (T-56, T-57): boots `tests/fixtures/testing_app`
through the real ASGI stack and gives every test a `TestClient` plus the S-2 test-binding
transaction (same pattern as `tests/test_spine_loop.py` and `tests/auth/conftest.py`).

`app` is deliberately **function**-scoped here, not session-scoped: the repo's root
`tests/conftest.py` purges `app.*`/`bootstrap.*`/... from `sys.modules` and resets
`Model.registry`/`Model.metadata` around *every* test (so one fixture app's classes never leak
into another's), which would sever a session-scoped `Post`/`User` class from its own mapper
mid-session. A real app's own `tests/conftest.py` has no such autouse reset, which is exactly why
T-55 specifies a session-scoped `app` fixture for the *shipped* plugin -- see
`tests/testing/test_plugin_end_to_end.py`, which boots the real plugin in its own subprocess
(a separate pytest run, with no interfering root conftest) and proves that behaviour instead.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from aso.database.scope import open_scope, reset_test_binding, set_test_binding
from aso.testing.client import TestClient

FIXTURE = Path(__file__).parent.parent / "fixtures" / "testing_app"


@pytest.fixture
async def app() -> AsyncIterator[object]:
    os.environ["APP_ENV"] = "testing"
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        fastapi_app = create_app()
        async with fastapi_app.router.lifespan_context(fastapi_app):
            import importlib

            # `app/models/user.py` is never imported by a controller/route in this fixture
            # (only by `config/auth.py`'s dotted provider string, resolved lazily), so the
            # `users` table would never exist unless we import it before `create_all`.
            importlib.import_module("app.models.user")

            from aso.database import Model
            from aso.database.engine import engine

            async with engine().begin() as conn:
                await conn.run_sync(Model.metadata.create_all)
            yield fastapi_app
    finally:
        sys.path.remove(str(FIXTURE))


@pytest.fixture(autouse=True)
async def db(app: object) -> AsyncIterator[object]:
    from aso.database.engine import engine

    async with engine().connect() as connection:
        transaction = await connection.begin()
        token = set_test_binding(connection)
        try:
            async with open_scope():
                yield connection
        finally:
            reset_test_binding(token)
            await transaction.rollback()
            from aso.session.drivers import clear_array_store

            clear_array_store()


@pytest.fixture
async def client(app: object) -> AsyncIterator[TestClient]:
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        await test_client.aclose()


@pytest.fixture
async def user():
    from app.models.user import User

    return await User.create(name="Jane", email="jane@example.com", password="secret1234")
