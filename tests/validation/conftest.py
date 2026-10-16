"""Fixture app + helpers for the validation package's end-to-end tests.

Mirrors `tests/test_spine_loop.py`'s pattern: a tiny real app (`tests/fixtures/validation_app`)
booted through the real middleware stack, driven with `httpx2`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "validation_app"

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


@pytest.fixture
async def client():
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        import importlib
        import pkgutil

        import app.models as models_pkg

        for info in pkgutil.iter_modules(models_pkg.__path__):
            importlib.import_module(f"app.models.{info.name}")
        from aso.database import Model
        from aso.database.engine import engine

        async with engine().begin() as conn:
            await conn.run_sync(Model.metadata.create_all)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            c.app = app  # exposed for the OpenAPI-schema test
            yield c
    finally:
        sys.path.remove(str(FIXTURE))
        for name in list(sys.modules):
            if name == "app" or name.startswith("app.") or name == "bootstrap" or name.startswith("bootstrap."):
                del sys.modules[name]
            if name == "config" or name.startswith("config."):
                del sys.modules[name]
            if name.startswith("routes"):
                del sys.modules[name]


@pytest.fixture
async def csrf_headers(client):
    """GET a page once (XSRF cookie + a Referer-worthy `back()` target), then the headers to send
    on a follow-up `POST`: `{**INERTIA, **csrf_headers}` for a web (Inertia) request."""
    await client.get("/forms/create")
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", ""), "Referer": "http://testserver/forms/create"}
