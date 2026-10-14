"""Isolation between the fixture apps in `tests/fixtures/`.

Every fixture app uses the same top-level package names (`app`, `bootstrap`, `routes`, `config`,
`database`) and declares models on the one shared `Model` registry. Before each test we purge
those modules and reset the registry, so a test never sees another fixture app's classes.
"""

from __future__ import annotations

import sys

import pytest

FIXTURE_PACKAGES = ("app", "bootstrap", "routes", "config", "database")


def reset_fixture_apps() -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in FIXTURE_PACKAGES:
            del sys.modules[name]
    from fastogram.database import Model

    from fastogram.cache import flush_all
    from fastogram.storage import storage

    storage.reset_fakes()
    flush_all()
    Model.registry.dispose()
    Model.metadata.clear()
    with_registry = getattr(Model.registry, "_class_registry", None)
    if isinstance(with_registry, dict):
        for key in [k for k in with_registry if not k.startswith("_")]:
            del with_registry[key]


@pytest.fixture(autouse=True)
def _isolate_fixture_apps():
    reset_fixture_apps()
    yield
    reset_fixture_apps()
