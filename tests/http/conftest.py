"""Fixture app + helpers for the HTTP end-to-end tests.

Mirrors `tests/test_spine_loop.py`'s pattern: a real app (`tests/fixtures/routing_app`) booted
through the real middleware stack, driven with `httpx2`.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "routing_app"
_FIXTURE_ROOTS = ("app", "bootstrap", "config", "routes")

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


def _purge_fixture_modules() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in _FIXTURE_ROOTS:
            del sys.modules[name]


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    _purge_fixture_modules()
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        from aso.database import Model
        from aso.database.engine import engine

        async with engine().begin() as conn:
            await conn.run_sync(Model.metadata.create_all)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))
        _purge_fixture_modules()


def xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


@pytest.fixture
async def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """GET any page once (XSRF cookie), then the headers for a follow-up unsafe request."""
    await client.get("/misc/ping")
    return xsrf(client)


@pytest.fixture
def mw_state(client: httpx.AsyncClient):
    """Clears the test middleware's recorded state. Depends on `client` so the fixture app's
    modules are already on `sys.path` when this imports them."""
    from app.http.controllers.misc_controller import INNER_RAN
    from app.http.middleware.bodypeek import PEEK
    from app.http.middleware.recording import RECORD
    from app.http.middleware.short_circuit import ShortCircuit  # noqa: F401

    RECORD.clear()
    PEEK.clear()
    INNER_RAN["value"] = False
    yield {"record": RECORD, "peek": PEEK, "inner_ran": INNER_RAN}
    RECORD.clear()
    PEEK.clear()
