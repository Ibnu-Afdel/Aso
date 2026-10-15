"""Boots the shared `tests/fixtures/routing_app` fixture (same one `tests/routing/` uses) just
far enough to get a compiled `RouteRegistry` -- no database, no HTTP client. `routes:generate`
needs nothing else (T-28 "How it works": no database or network access).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "routing_app"
_FIXTURE_ROOTS = ("app", "bootstrap", "config", "routes")


def _purge_fixture_modules() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in _FIXTURE_ROOTS:
            del sys.modules[name]


@pytest.fixture
def registry() -> Iterator[object]:
    from fastogram.routing.registry import current_registry

    _purge_fixture_modules()
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        create_app()
        yield current_registry()
    finally:
        sys.path.remove(str(FIXTURE))
        _purge_fixture_modules()
