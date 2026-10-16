"""`storage.fake()` leaves the swapped disks in place until `reset_fakes()` runs (T-43); undo it
after every test in this directory so fakes never leak between tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_storage_fakes():
    from aso.storage import storage

    yield
    storage.reset_fakes()
