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
    from aso.auth.gate import Gate
    from aso.auth.password_broker import _reset_for_tests as reset_password_brokers
    from aso.cache import flush_all
    from aso.console.registry import reset_registry as reset_console_registry
    from aso.console.schedule import schedule as console_schedule
    from aso.database import Model
    from aso.events import reset_events
    from aso.mail import reset_mail
    from aso.queue import reset_queue
    from aso.storage import storage

    # User/closure commands and schedule events are registered by a fixture app's
    # `app/console/commands/*.py` / `routes/console.py` (T-50, T-45), not tied to module
    # identity the way the purge above is -- drop them explicitly so one fixture app's console
    # commands/schedule never leak into the next. Framework commands (`keep="framework"`,
    # the default) are process-global and stay registered.
    reset_console_registry()
    console_schedule.clear()
    storage.reset_fakes()
    flush_all()
    # `Gate._gates`/`_policies`/`_policy_cache` are process-global (T-39), and policy lookups are
    # cached by *class object*: a fixture app's `app.policies.*` classes are fresh every test (its
    # modules are purged above), so a stale cache entry would hold a dead class and never match
    # the new one -- harmless, but it leaks memory for the life of the test process without this.
    # `Gate.define()`/`Gate.policy()` calls in a fixture app's `create_app()` would otherwise also
    # accumulate across fixture apps that reuse the same ability name with a different callback.
    Gate._reset_for_tests()
    reset_password_brokers()
    # Event._listeners/Mail._fake/Queue._fake are process-global (T-46, T-41, T-42): a fixture
    # app's `create_app()` in `bootstrap/app.py` calls `Event.listen()` every time it runs, and a
    # test that leaves `Event.fake()`/`Mail.fake()`/`Queue.fake()` on would silently swallow the
    # next test's real dispatch/send. The listener registry itself is also cleared, not just the
    # fakes, since fixture modules are purged and reimported above (see `reset_events()`'s
    # docstring for why stale class-keyed entries would otherwise accumulate).
    reset_events()
    reset_mail()
    reset_queue()
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
