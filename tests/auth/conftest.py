"""Fixtures for `tests/auth/` unit tests that need a database or a fake request context, without
going through the full HTTP stack (see `test_auth_app_stack.py` for that).

Follows the same S-2 binding pattern as `tests/database/conftest.py` (one connection + outer
transaction per test, rolled back at the end); model classes are defined inside each test, never
at module level, since `tests/conftest.py` resets `Model.registry`/`Model.metadata` around every
test.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from aso import context
from aso.database.engine import configure, install_sqlite_recipe
from aso.database.scope import open_scope, reset_test_binding, set_test_binding
from aso.session.store import Session


@pytest.fixture(scope="session")
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


class _FakeRequest:
    def __init__(self, cookies: dict[str, str] | None = None, client_ip: str = "127.0.0.1") -> None:
        self.cookies = cookies or {}
        self._client_ip = client_ip

    def client_ip(self) -> str:
        return self._client_ip


@pytest.fixture
def request_context():
    """Enter a fake request context with a real `Session`, so `session()`/`auth()` work.

    Returns the active `RequestContext`; call `.request.cookies["x"] = "y"` etc. to tweak it.
    """

    def _use(cookies: dict[str, str] | None = None) -> context.RequestContext:
        session = Session(id="test-session")
        request = _FakeRequest(cookies=cookies)
        ctx = context.RequestContext(scope={}, request=request, session=session, group="web")
        context.enter(ctx)
        return ctx

    return _use


@pytest.fixture(autouse=True)
def _auth_config() -> None:
    """A minimal `config/auth.py`-equivalent for unit tests (most override the model, see
    `user_model` below -- `tests/conftest.py` resets all config between tests)."""
    from aso.config import set_config

    set_config("auth.defaults", {"guard": "web", "passwords": "users"})
    set_config("auth.guards", {"web": {"driver": "session", "provider": "users"}})
    set_config("auth.passwords", {"users": {"provider": "users", "table": "password_reset_tokens", "expire": 60, "throttle": 60}})
    set_config("app.key", "base64:dGVzdGluZy1rZXktdGVzdGluZy1rZXktMzJieXQ9MTM=")
    set_config("app.url", "http://testserver")


@pytest.fixture
def user_model(monkeypatch: pytest.MonkeyPatch):
    """`user_model(SomeLocalUserClass)`: point `aso.auth.guard._user_model()` at a class
    defined inside the test itself (never at module level, see this file's docstring)."""

    def _set(model_cls: type) -> type:
        monkeypatch.setattr("aso.auth.guard._user_model", lambda: model_cls)
        return model_cls

    return _set
