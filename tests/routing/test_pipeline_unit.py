"""White-box unit tests for `fastogram.routing.pipeline` (T-11): alias resolution, priority
sorting, custom groups, `without_middleware`, and controller-declared `only`/`except_`.

These construct a bare `Application` + `RouteDefinition` and call `resolve_items()` directly --
no FastAPI app, no ASGI call -- since the resolver is pure data transformation. Runtime execution
order (that the resolved pipeline actually runs in this order) is covered end-to-end in
`tests/routing/test_feature_routes.py` (`/mw/order`, `/mw/priority`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fastogram.foundation.application import Application
from fastogram.http.controller import Controller, ControllerMiddleware
from fastogram.routing.pipeline import _expand, resolve_items
from fastogram.routing.registry import RouteDefinition

NOOP = "fastogram.http.middleware:Middleware"


@pytest.fixture
def app() -> Application:
    application = Application(Path("."))
    application.middleware_config.alias({"alpha": NOOP, "beta": NOOP, "gamma": NOOP})
    return application


def test_resolve_items_always_appends_the_bindings_step(app: Application):
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    items = resolve_items(app, d)
    assert items[-1].key == "bindings"


def test_default_order_is_preserved_when_none_are_prioritised(app: Application):
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    d.middleware("beta", "alpha")
    items = resolve_items(app, d)
    assert [i.key for i in items] == ["beta", "alpha", "bindings"]


def test_priority_reorders_listed_middleware_regardless_of_registration_order(app: Application):
    app.middleware_config.priority(["alpha", "beta", "bindings"])
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    d.middleware("beta", "alpha")
    items = resolve_items(app, d)
    assert [i.key for i in items] == ["alpha", "beta", "bindings"]


def test_priority_only_reorders_from_the_first_prioritised_item_onward(app: Application):
    """Laravel's priority sort: items before the first prioritised one keep their place."""
    app.middleware_config.priority(["alpha", "beta", "bindings"])
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    d.middleware("gamma", "beta", "alpha")
    items = resolve_items(app, d)
    assert [i.key for i in items] == ["gamma", "alpha", "beta", "bindings"]


def test_without_middleware_excludes_by_alias_key(app: Application):
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    d.middleware("alpha", "beta")
    d.without_middleware("alpha")
    items = resolve_items(app, d)
    assert [i.key for i in items] == ["beta", "bindings"]


def test_custom_group_expands_into_its_members_preserving_order(app: Application):
    app.middleware_config.group("grp", ["beta", "alpha"])
    d = RouteDefinition(methods=["GET"], path="/x", action=None)
    d.middleware("grp")
    items = resolve_items(app, d)
    assert [i.key for i in items] == ["beta", "alpha", "bindings"]


def test_middleware_with_params_keeps_them_on_the_item(app: Application):
    items = _expand(app, "alpha:editor,admin")
    assert items[0].key == "alpha"
    assert items[0].params == ("editor", "admin")


def test_unknown_alias_raises_only_when_actually_expanded(app: Application):
    """An undefined alias never used anywhere never raises; `_expand` only runs for middleware a
    route actually lists -- so the error is naturally scoped to the routes that use it."""
    with pytest.raises(RuntimeError, match=r"\[ghost\] is not defined"):
        _expand(app, "ghost")


def test_controller_declared_middleware_is_merged_in(app: Application):
    class C(Controller):
        @staticmethod
        def middleware():
            return ["alpha"]

        async def action(self): ...

    d = RouteDefinition(methods=["GET"], path="/x", action=[C, "action"])
    items = resolve_items(app, d)
    assert "alpha" in [i.key for i in items]


def test_controller_middleware_only_limits_it_to_named_actions(app: Application):
    class C(Controller):
        @staticmethod
        def middleware():
            return [ControllerMiddleware("alpha", only=["gated"])]

        async def gated(self): ...
        async def open_(self): ...

    gated = RouteDefinition(methods=["GET"], path="/x", action=[C, "gated"])
    open_ = RouteDefinition(methods=["GET"], path="/y", action=[C, "open_"])
    assert "alpha" in [i.key for i in resolve_items(app, gated)]
    assert "alpha" not in [i.key for i in resolve_items(app, open_)]


def test_controller_middleware_except_excludes_named_actions(app: Application):
    class C(Controller):
        @staticmethod
        def middleware():
            return [ControllerMiddleware("alpha", except_=["open_"])]

        async def gated(self): ...
        async def open_(self): ...

    gated = RouteDefinition(methods=["GET"], path="/x", action=[C, "gated"])
    open_ = RouteDefinition(methods=["GET"], path="/y", action=[C, "open_"])
    assert "alpha" in [i.key for i in resolve_items(app, gated)]
    assert "alpha" not in [i.key for i in resolve_items(app, open_)]


def test_without_middleware_also_overrides_controller_declared_middleware(app: Application):
    class C(Controller):
        @staticmethod
        def middleware():
            return ["alpha"]

        async def action(self): ...

    d = RouteDefinition(methods=["GET"], path="/x", action=[C, "action"])
    d.without_middleware("alpha")
    assert "alpha" not in [i.key for i in resolve_items(app, d)]
