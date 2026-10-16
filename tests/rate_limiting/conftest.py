"""Fixture app + helpers for the rate-limiting end-to-end tests (T-44).

Mirrors `tests/routing/conftest.py`'s pattern: a real app (`tests/fixtures/throttle_app`) booted
through the real middleware stack, driven with `httpx2`, so the `throttle:` alias is exercised
exactly as a real request would hit it (route compiling, priority sort, exception boundary).
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "throttle_app"
_FIXTURE_ROOTS = ("app", "bootstrap", "config", "routes")


def _purge_fixture_modules() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in _FIXTURE_ROOTS:
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _reset_rate_limiting_state():
    """Cache stores and named limiters are process-global; isolate every test from the last."""
    from aso.cache.manager import flush_all
    from aso.rate_limiting.limiter import _reset_for_tests

    flush_all()
    _reset_for_tests()
    yield
    flush_all()
    _reset_for_tests()


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
