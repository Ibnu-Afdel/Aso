"""Testing support (T-55, T-56, T-57): `TestClient`/`TestResponse` (HTTP + Inertia), database
assertions, `seed()` and `LogCapture` re-exports, and the pytest plugin `aso.testing.plugin`.

See `aso.testing.arch` for architecture tests (T-58).
"""

from __future__ import annotations

from aso.database.seeder import seed
from aso.log.testing import LogCapture
from aso.testing.client import TestClient
from aso.testing.database import (
    assert_database_count,
    assert_database_has,
    assert_database_missing,
    assert_model_exists,
    assert_model_missing,
)
from aso.testing.response import TestResponse

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
