"""`aso.testing.plugin` (T-55): the pytest plugin a Aso app's `tests/conftest.py`
loads with `pytest_plugins = ["aso.testing.plugin"]` (and the entry point in
`pyproject.toml`, which this library's own suite disables with `-p no:aso`).

Boots the app from the project's `bootstrap/app.py` once per session, migrates (or
`create_all`-s) the schema once, and isolates every test inside a rolled-back database
transaction (T-57), resetting fakes and the array session store between tests.
"""

from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from aso.database.scope import open_scope, reset_test_binding, set_test_binding
from aso.database.seeder import seed
from aso.log.testing import LogCapture
from aso.testing.client import TestClient

__all__ = ["LogCapture", "seed"]


def pytest_configure(config: pytest.Config) -> None:
    """Sets `APP_ENV=testing` before anything imports `bootstrap/app.py` (T-55)."""
    os.environ["APP_ENV"] = "testing"
    root = str(config.rootpath)
    if root not in sys.path:
        sys.path.insert(0, root)


def _install_exception_capture() -> None:
    """A `respond()` callback that stashes the reported exception on the request context, so
    `TestResponse` can show it in a failing assertion's message (T-56 "How it works")."""
    from aso.foundation.application import current_application

    application = current_application()
    if application is None:
        return
    config = application.exceptions_config
    if any(getattr(cb, "__aso_testing__", False) for cb in config.respond_callbacks):
        return  # idempotent: harmless if `pytest_configure` + the `app` fixture run more than once

    def _capture(response: Any, exc: BaseException, request: Any) -> Any:
        from aso import context

        ctx = context.current()
        if ctx is not None:
            ctx.extras["testing.exception"] = exc
        return response

    _capture.__aso_testing__ = True  # type: ignore[attr-defined]
    config.respond(_capture)


async def _ensure_schema() -> None:
    """Migrations once per session (`upgrade head`), or `Model.metadata.create_all` when the
    project has no `database/migrations/` files yet (T-55 "Test environment")."""
    from aso.database import Model
    from aso.database.engine import engine
    from aso.foundation.paths import base_path

    base = base_path()
    migrations_dir = base / "database" / "migrations"
    has_migrations = migrations_dir.is_dir() and any(migrations_dir.glob("*.py"))
    if has_migrations:
        from aso.console import migrations as console_migrations

        console_migrations.import_app_models(base)
        await console_migrations.migrate()
    else:
        with contextlib.suppress(ImportError):
            _import_app_models_best_effort(base)
        eng = engine()
        async with eng.begin() as conn:
            await conn.run_sync(Model.metadata.create_all)


def _import_app_models_best_effort(base: Path) -> None:
    directory = base / "app" / "models"
    if not directory.is_dir():
        return
    import importlib.util

    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"app.models.{path.stem}"
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)


def _reset_between_tests() -> None:
    """Fakes and the `array` session store reset after every test (T-55 "The plugin provides").

    Deliberately does **not** call `aso.events.reset_events()`: that also clears the
    listener registry, which `create_app()` only populates once for this whole session.
    `Event.reset()` alone drops the fake/recorded dispatches and leaves listeners registered.
    """
    from aso.cache import flush_all
    from aso.events import Event
    from aso.mail import reset_mail
    from aso.queue import reset_queue
    from aso.session.drivers import clear_array_store
    from aso.storage import storage

    clear_array_store()
    reset_mail()
    reset_queue()
    Event.reset()
    storage.reset_fakes()
    flush_all()


@pytest.fixture(scope="session")
async def app() -> AsyncIterator[Any]:
    """The app from `bootstrap.app.create_app()`, booted once, with the ASGI lifespan run for
    the whole session (`ASGITransport` never runs it itself, T-56 "How it works")."""
    from bootstrap.app import create_app

    fastapi_app = create_app()
    async with fastapi_app.router.lifespan_context(fastapi_app):
        await _ensure_schema()
        _install_exception_capture()
        yield fastapi_app


@pytest.fixture(autouse=True)
async def db(app: Any) -> AsyncIterator[Any]:
    """One connection + one outer transaction per test; every scope (the test's own, and each
    request's `DatabaseScope`) joins it with `create_savepoint` (T-57)."""
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
            _reset_between_tests()


@pytest.fixture
async def client(app: Any) -> AsyncIterator[TestClient]:
    """A `TestClient` for `app`, with a fresh/empty cookie jar for every test (T-56)."""
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        await test_client.aclose()
