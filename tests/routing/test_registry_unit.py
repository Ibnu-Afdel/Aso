"""White-box unit tests for `aso.routing.registry` (T-10): recording routes, groups and
resource expansion, without compiling a full FastAPI app.

These push a fresh `RouteRegistry` onto the module's contextvar directly (the same one
`load_routes()` uses), call the public `Route` facade, and inspect the recorded
`RouteDefinition` objects. This is the fast path for everything that is pure bookkeeping;
behaviour that depends on the compiled ASGI stack is covered end-to-end in
`tests/routing/test_feature_routes.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from aso.routing import registry as reg_mod
from aso.routing.registry import Route, RouteRegistry, route, route_list


class FakeController:
    @staticmethod
    async def index(): ...
    @staticmethod
    async def create(): ...
    @staticmethod
    async def store(): ...
    @staticmethod
    async def show(photo): ...
    @staticmethod
    async def edit(photo): ...
    @staticmethod
    async def update(photo): ...
    @staticmethod
    async def destroy(photo): ...


@contextmanager
def fresh_registry() -> Iterator[RouteRegistry]:
    reg = RouteRegistry()
    token = reg_mod._registry.set(reg)
    gtoken = reg_mod._current_group.set("web")
    try:
        yield reg
    finally:
        reg_mod._registry.reset(token)
        reg_mod._current_group.reset(gtoken)


# ---------------------------------------------------------------- verbs


def test_every_verb_records_the_right_methods():
    with fresh_registry():
        assert Route.get("/x", FakeController.index).methods == ["GET", "HEAD"]
        assert Route.post("/x", FakeController.index).methods == ["POST"]
        assert Route.put("/x", FakeController.index).methods == ["PUT"]
        assert Route.patch("/x", FakeController.index).methods == ["PATCH"]
        assert Route.delete("/x", FakeController.index).methods == ["DELETE"]
        assert Route.options("/x", FakeController.index).methods == ["OPTIONS"]
        assert Route.match(["get", "post"], "/x", FakeController.index).methods == ["GET", "POST"]
        assert set(Route.any("/x", FakeController.index).methods) == {
            "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
        }


def test_redirect_and_permanent_redirect_and_inertia_and_fallback_register_definitions():
    with fresh_registry() as reg:
        Route.redirect("/old", "/new")
        Route.permanent_redirect("/legacy", "/new")
        Route.inertia("/about", "about")
        Route.fallback(FakeController.index)
        kinds = [(d.methods, d.is_fallback) for d in reg.definitions]
        assert kinds == [
            (["GET", "HEAD"], False),
            (["GET", "HEAD"], False),
            (["GET", "HEAD"], False),
            (["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], True),
        ]


# ---------------------------------------------------------------- groups


def test_groups_merge_prefix_name_and_middleware_when_nested():
    with fresh_registry() as reg:
        with Route.prefix("admin").name("admin.").middleware("one").group():
            Route.get("/users", FakeController.index).name("users.index")
            with Route.prefix("reports").name("reports.").group():
                Route.get("/sales", FakeController.index).name("sales")
        by_name = {d.route_name: d for d in reg.definitions}
        assert by_name["admin.users.index"].path == "/admin/users"
        assert by_name["admin.users.index"].middleware_list == ["one"]
        assert by_name["admin.reports.sales"].path == "/admin/reports/sales"
        assert by_name["admin.reports.sales"].middleware_list == ["one"]


def test_controller_group_accepts_bare_string_actions():
    with fresh_registry() as reg:
        with Route.controller(FakeController).group():
            Route.get("/items/{photo}", "show")
            Route.post("/items", "store")
        assert reg.definitions[0].action == [FakeController, "show"]
        assert reg.definitions[1].action == [FakeController, "store"]


def test_bare_string_action_outside_a_controller_group_raises():
    with fresh_registry():
        with pytest.raises(RuntimeError):
            Route.get("/items/{photo}", "show")


def test_wheres_set_named_patterns():
    with fresh_registry():
        d = Route.get("/x/{id}", FakeController.index)
        d.where_number("id")
        assert d.wheres == {"id": r"[0-9]+"}
        d2 = Route.get("/y/{name}", FakeController.index)
        d2.where_alpha("name")
        assert d2.wheres == {"name": r"[a-zA-Z]+"}
        d3 = Route.get("/z/{uuid}", FakeController.index)
        d3.where_uuid("uuid")
        assert d3.wheres == {"uuid": "__uuid__"}
        d4 = Route.get("/w/{path}", FakeController.index)
        d4.where("path", r".*")
        assert d4.wheres == {"path": r".*"}


# ---------------------------------------------------------------- resources


def test_resource_registers_all_seven_conventional_routes():
    with fresh_registry() as reg:
        Route.resource("photos", FakeController)
        rows = {d.route_name: (d.methods, d.path) for d in reg.definitions}
        assert rows["photos.index"] == (["GET", "HEAD"], "/photos")
        assert rows["photos.create"] == (["GET", "HEAD"], "/photos/create")
        assert rows["photos.store"] == (["POST"], "/photos")
        assert rows["photos.show"] == (["GET", "HEAD"], "/photos/{photo}")
        assert rows["photos.edit"] == (["GET", "HEAD"], "/photos/{photo}/edit")
        assert rows["photos.update"] == (["PUT", "PATCH"], "/photos/{photo}")
        assert rows["photos.destroy"] == (["DELETE"], "/photos/{photo}")


def test_resource_skips_actions_the_controller_does_not_define():
    class Partial:
        @staticmethod
        async def index(): ...
        @staticmethod
        async def show(thing): ...

    with fresh_registry() as reg:
        Route.resource("things", Partial)
        names = {d.route_name for d in reg.definitions}
        assert names == {"things.index", "things.show"}


def test_api_resource_excludes_create_and_edit_even_when_defined():
    with fresh_registry() as reg:
        Route.api_resource("photos", FakeController)
        names = {d.route_name for d in reg.definitions}
        assert "photos.create" not in names
        assert "photos.edit" not in names
        assert names == {"photos.index", "photos.store", "photos.show", "photos.update", "photos.destroy"}


def test_resource_only_removes_the_unwanted_definitions_from_the_registry():
    with fresh_registry() as reg:
        Route.resource("photos", FakeController).only("index", "show")
        assert {d.route_name for d in reg.definitions} == {"photos.index", "photos.show"}


def test_resource_except_removes_just_those_actions():
    with fresh_registry() as reg:
        Route.resource("photos", FakeController).except_("destroy")
        assert "photos.destroy" not in {d.route_name for d in reg.definitions}
        assert "photos.index" in {d.route_name for d in reg.definitions}


def test_resource_names_overrides_the_route_name():
    with fresh_registry():
        reg_result = Route.resource("photos", FakeController).names({"index": "gallery"})
        assert reg_result.defs["index"].route_name == "gallery"
        assert reg_result.defs["show"].route_name == "photos.show"


def test_resource_parameters_overrides_the_path_segment():
    with fresh_registry():
        result = Route.resource("photos", FakeController).parameters({"photos": "image"})
        assert result.defs["show"].path == "/photos/{image}"
        assert result.defs["update"].path == "/photos/{image}"


def test_resource_middleware_applies_to_every_registered_action():
    with fresh_registry():
        result = Route.resource("photos", FakeController).middleware("auth")
        assert all("auth" in d.middleware_list for d in result.defs.values())


def test_nested_resource_paths_and_names():
    with fresh_registry() as reg:
        Route.resource("posts.comments", FakeController)
        by_name = {d.route_name: d.path for d in reg.definitions}
        assert by_name["posts.comments.index"] == "/posts/{post}/comments"
        assert by_name["posts.comments.show"] == "/posts/{post}/comments/{comment}"


def test_shallow_drops_the_parent_segment_from_member_routes_only():
    with fresh_registry():
        result = Route.resource("posts.comments", FakeController)
        result.shallow()
        assert result.defs["show"].path == "/comments/{comment}"
        assert result.defs["edit"].path == "/comments/{comment}/edit"
        assert result.defs["update"].path == "/comments/{comment}"
        assert result.defs["destroy"].path == "/comments/{comment}"
        # collection actions are untouched: they never carried a {comment} segment.
        assert result.defs["index"].path == "/posts/{post}/comments"
        assert result.defs["store"].path == "/posts/{post}/comments"


# ---------------------------------------------------------------- route() / route_list()


def test_route_fn_substitutes_params_and_appends_extra_keys_as_query_string():
    with fresh_registry():
        Route.get("/posts/{post}", FakeController.index).name("posts.show")
        assert route("posts.show", {"post": 5}) == "/posts/5"
        assert route("posts.show", {"post": 5, "tab": "comments"}) == "/posts/5?tab=comments"


def test_route_fn_reads_the_models_id_by_default():
    class Model:
        id = 7

    with fresh_registry():
        Route.get("/posts/{post}", FakeController.index).name("posts.show")
        assert route("posts.show", Model()) == "/posts/7"


def test_route_fn_reads_the_binding_field_for_a_bound_param():
    class Model:
        id = 7
        slug = "hello"

    with fresh_registry():
        Route.get("/posts/{post:slug}", FakeController.index).name("posts.show")
        assert route("posts.show", Model()) == "/posts/hello"


def test_route_fn_unknown_name_raises_keyerror():
    with fresh_registry():
        with pytest.raises(KeyError):
            route("nope")


def test_route_fn_absolute_prefixes_app_url(monkeypatch: pytest.MonkeyPatch):
    from aso.config import set_config

    set_config("app.url", "https://example.com")
    with fresh_registry():
        Route.get("/posts/{post}", FakeController.index).name("posts.show")
        assert route("posts.show", {"post": 5}, absolute=True) == "https://example.com/posts/5"


def test_route_list_reports_method_uri_name_action_and_middleware():
    with fresh_registry() as reg:
        Route.get("/photos/{photo}", [FakeController, "show"]).name("photos.show").middleware("auth")
        rows = route_list(reg)
        row = next(r for r in rows if r["name"] == "photos.show")
        assert row["method"] == "GET|HEAD"
        assert row["uri"] == "/photos/{photo}"
        assert "FakeController" in row["action"]
        assert row["middleware"] == ["auth"]
        assert row["group"] == "web"
