import pytest

from database.factories.user_factory import UserFactory

# `fastogram` ships a `pytest11` entry point that auto-loads `fastogram.testing.plugin` for any
# project that depends on it (see `fastogram`'s own `pyproject.toml`). Do NOT also add
# `pytest_plugins = ["fastogram.testing.plugin"]` here: pluggy registers the entry-point copy
# under the name "fastogram" and an explicit `pytest_plugins` import of the same module under
# "fastogram.testing.plugin", and raises `ValueError: Plugin already registered under a
# different name` because they are the identical module object. This is a deviation from an
# earlier draft of T-55's example `tests/conftest.py` -- see the build report.


@pytest.fixture
async def user():
    return await UserFactory.new().create()
