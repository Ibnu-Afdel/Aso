"""Process-global cache state isolation for `tests/cache/` (T-44)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_cache_state():
    from aso.cache.manager import flush_all

    flush_all()
    yield
    flush_all()
