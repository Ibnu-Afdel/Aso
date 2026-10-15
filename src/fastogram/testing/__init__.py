"""Testing support (T-55, T-56, T-57): `TestClient`/`TestResponse` (HTTP + Inertia), database
assertions, `seed()` and `LogCapture` re-exports, and the pytest plugin `fastogram.testing.plugin`.

See `fastogram.testing.arch` for architecture tests (T-58).
"""

from __future__ import annotations

from fastogram.database.seeder import seed
from fastogram.log.testing import LogCapture
from fastogram.testing.client import TestClient
from fastogram.testing.database import (
    assert_database_count,
    assert_database_has,
    assert_database_missing,
    assert_model_exists,
    assert_model_missing,
)
from fastogram.testing.response import TestResponse

__all__ = [
    "LogCapture",
    "TestClient",
    "TestResponse",
    "assert_database_count",
    "assert_database_has",
    "assert_database_missing",
    "assert_model_exists",
    "assert_model_missing",
    "seed",
]
