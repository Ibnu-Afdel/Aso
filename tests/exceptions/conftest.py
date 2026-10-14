"""Fixtures for the T-20 error-handling tests: the `tests/fixtures/errors` app.

`tests/fixtures/blog` (used by `tests/test_spine_loop.py`) uses the same top-level package names
(`app`, `bootstrap`, `config`, `routes`). Both fixtures' `client`-style fixtures rely on
`sys.path` tricks and Python caches imports in `sys.modules`, so we purge our own fixture's
modules on the way in *and* out -- otherwise whichever fixture app happened to import first would
leak its cached `app.*`/`config.*` modules into the other one's test run.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "errors"
_FIXTURE_ROOTS = ("app", "bootstrap", "config", "routes")


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
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))
        _purge_fixture_modules()


@pytest.fixture
async def debug_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    """Same app, but booted with `APP_DEBUG=true` (production rendering is the `client` default)."""
    monkeypatch.setenv("APP_DEBUG", "true")
    _purge_fixture_modules()
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))
        _purge_fixture_modules()


def xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}
