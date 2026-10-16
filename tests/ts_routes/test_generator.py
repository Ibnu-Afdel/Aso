"""Unit tests for `aso.routing.ts_routes` (T-28), against the shared fixture app
`tests/fixtures/routing_app` (resources, `{post:slug}` binding, optional/typed params, a
single-action controller, reserved-word-safe exports). No npm/Node is needed: these tests only
check the generated TypeScript *text*, not that it compiles (that is `npm run build`'s job, run
separately as part of "prove it builds").
"""

from __future__ import annotations

from pathlib import Path

from aso.routing.registry import RouteRegistry
from aso.routing.ts_routes import _safe_export, default_method, generate


def test_default_method_prefers_non_head():
    assert default_method(["GET", "HEAD"]) == "get"
    assert default_method(["PUT", "PATCH"]) == "put"
    assert default_method(["POST"]) == "post"
    assert default_method(["HEAD"]) == "get"  # degenerate: no non-HEAD method


def test_safe_export_escapes_js_reserved_words():
    assert _safe_export("delete") == "delete_"
    assert _safe_export("show") == "show"


def test_generate_writes_runtime_helper(tmp_path: Path, registry: RouteRegistry) -> None:
    written = generate(tmp_path, registry)
    runtime = tmp_path / "resources" / "js" / "wayfinder" / "index.ts"
    assert runtime.is_file()
    assert "export function buildPath" in runtime.read_text()
    assert str(runtime.relative_to(tmp_path)) in written


def test_generate_groups_routes_by_name_prefix(tmp_path: Path, registry: RouteRegistry) -> None:
    generate(tmp_path, registry)
    js = tmp_path / "resources" / "js"

    top_level = (js / "routes" / "index.ts").read_text()
    assert "export const gated" in top_level
    assert "export const open" in top_level
    assert "export const invoke" in top_level

    posts = (js / "routes" / "posts" / "index.ts").read_text()
    for export in ("index", "create", "store", "show", "show_by_slug", "edit", "update", "destroy"):
        assert f"export const {export}" in posts

    # "admin.users.index" -> routes/admin/users/index.ts export "index"
    admin_users = (js / "routes" / "admin" / "users" / "index.ts").read_text()
    assert "export const index" in admin_users

    # "admin.reports.sales" -> routes/admin/reports/index.ts export "sales"
    admin_reports = (js / "routes" / "admin" / "reports" / "index.ts").read_text()
    assert "export const sales" in admin_reports


def test_generate_types_model_bound_and_where_params(tmp_path: Path, registry: RouteRegistry) -> None:
    generate(tmp_path, registry)
    posts = (tmp_path / "resources" / "js" / "routes" / "posts" / "index.ts").read_text()

    # `show(post: Post)` binds by the (integer) primary key -> "number".
    assert "export type ShowArgs = number | " in posts
    # `show_by_slug(post: Post)` on `/posts-by-slug/{post:slug}` binds by the `slug` column
    # (a `String`) -> "string".
    assert "export type Show_by_slugArgs = string | " in posts

    top_level = (tmp_path / "resources" / "js" / "routes" / "index.ts").read_text()
    # `Route.post("/invoke/{n}", PingInvokable).where_number("n")`, `n: int` -> "number".
    assert "export type InvokeArgs = number | " in top_level

    invokable = (
        tmp_path / "resources" / "js" / "actions" / "app" / "http" / "controllers" / "ping_invokable.ts"
    ).read_text()
    assert "export type _defaultArgs = number | " in invokable


def test_generate_optional_param_keeps_question_mark_in_template(tmp_path: Path, registry: RouteRegistry) -> None:
    generate(tmp_path, registry)
    misc = (tmp_path / "resources" / "js" / "routes" / "misc" / "index.ts").read_text()
    assert '"/misc/archive/{year?}"' in misc


def test_generate_actions_group_by_controller_module(tmp_path: Path, registry: RouteRegistry) -> None:
    generate(tmp_path, registry)
    actions = tmp_path / "resources" / "js" / "actions"

    post_controller = (actions / "app" / "http" / "controllers" / "post_controller.ts").read_text()
    for method in ("index", "create", "store", "show", "show_by_slug", "edit", "update", "destroy"):
        assert f"export const {method}" in post_controller
    assert "export default {" in post_controller
    assert "show_by_slug: show_by_slug," in post_controller

    # Single-action controller (`__call__`): default export only, no named export of the method.
    invokable = (actions / "app" / "http" / "controllers" / "ping_invokable.ts").read_text()
    assert "export default _default;" in invokable
    assert "PingInvokable" in invokable


def test_with_form_flag_adds_form_helper(tmp_path: Path, registry: RouteRegistry) -> None:
    without = tmp_path / "without"
    with_flag = tmp_path / "with"
    generate(without, registry, with_form=False)
    generate(with_flag, registry, with_form=True)

    posts_without = (without / "resources" / "js" / "routes" / "posts" / "index.ts").read_text()
    posts_with = (with_flag / "resources" / "js" / "routes" / "posts" / "index.ts").read_text()
    assert "form:" not in posts_without
    assert "form: (" in posts_with


def test_skip_routes_and_skip_actions_flags(tmp_path: Path, registry: RouteRegistry) -> None:
    generate(tmp_path, registry, skip_routes=True, skip_actions=True)
    js = tmp_path / "resources" / "js"
    assert not (js / "routes").exists()
    assert not (js / "actions").exists()
    assert (js / "wayfinder" / "index.ts").is_file()


def test_generate_is_idempotent_and_deterministic(tmp_path: Path, registry: RouteRegistry) -> None:
    first = generate(tmp_path, registry)
    assert any(first.values()), "first run should write files"

    posts_path = tmp_path / "resources" / "js" / "routes" / "posts" / "index.ts"
    before = posts_path.read_text()

    second = generate(tmp_path, registry)
    assert not any(second.values()), "nothing changed, nothing should be rewritten"
    assert posts_path.read_text() == before


def test_generate_clears_stale_files(tmp_path: Path, registry: RouteRegistry) -> None:
    js = tmp_path / "resources" / "js"
    stale = js / "routes" / "ghost" / "index.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("// stale\n")

    generate(tmp_path, registry)
    assert not stale.exists()
