"""T-56: `assert_inertia()`/`AssertableInertia`, flash-after-redirect, partial reloads and
deferred props, for both an HTML first visit and a JSON Inertia visit of the same page."""

from __future__ import annotations

import pytest

from aso.testing.client import TestClient


async def test_first_visit_html_and_inertia_visit_parse_the_same_page(client: TestClient) -> None:
    html_response = await client.get("/posts")
    html_response.assert_inertia(lambda page: page.component("posts/index").etc())

    json_response = await client.inertia().get("/posts")
    json_response.assert_header("X-Inertia", "true")
    json_response.assert_inertia(lambda page: page.component("posts/index").etc())


async def test_component_url_and_version(client: TestClient) -> None:
    response = await client.inertia().get("/posts")
    response.assert_inertia(lambda page: page.component("posts/index").url("/posts").version("").etc())


async def test_has_with_count_and_scoped_callback(client: TestClient, user) -> None:
    await client.acting_as(user).post("/posts", json={"title": "Scoped post"})

    response = await client.inertia().get("/posts")
    response.assert_inertia(
        lambda page: page.component("posts/index").has(
            "posts.data",
            1,
            lambda post: post.where("title", "Scoped post").has("id").has("user_id").etc(),
        ).where("posts.total", 1)
    )


async def test_strict_scope_fails_without_etc(client: TestClient, user) -> None:
    await client.acting_as(user).post("/posts", json={"title": "Strict post"})
    response = await client.inertia().get("/posts")

    with pytest.raises(AssertionError) as excinfo:
        response.assert_inertia(
            lambda page: page.has("posts.data", 1, lambda post: post.where("title", "Strict post"))
        )
    assert "etc()" in str(excinfo.value)


async def test_has_all_missing_and_missing_all(client: TestClient) -> None:
    response = await client.inertia().get("/posts")
    response.assert_inertia(
        lambda page: page.has_all("posts", "notifications", "stats", "auth")
        .missing("sidebar")  # deferred: not sent on the initial visit (only in `deferredProps`)
        .missing("not-a-real-prop")
        .missing_all("also-not-real", "nor-this")
        .etc()
    )


async def test_where_and_where_type(client: TestClient, user) -> None:
    response = await client.acting_as(user).inertia().get("/posts")
    response.assert_inertia(
        lambda page: page.where("auth.user.id", user.id)
        .where("auth.user.name", lambda v: v == "Jane")
        .where_type("posts.total", "integer")
        .where_type("posts.data", "array")
        .etc()
    )


async def test_merge_once_and_deferred_metadata(client: TestClient) -> None:
    response = await client.inertia().get("/posts")
    response.assert_inertia(
        lambda page: page.has_merge("notifications").has_once("stats").has_deferred("sidebar").etc()
    )


async def test_flash_after_redirect(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/posts", json={"title": "Flashed post"})
    response.assert_redirect_to_route("posts.index")
    response.assert_inertia_flash("success", "Post created.")


async def test_has_flash_on_the_next_page(client: TestClient, user) -> None:
    await client.acting_as(user).post("/posts", json={"title": "Another flashed post"})
    response = await client.acting_as(user).inertia().get("/posts")
    response.assert_inertia(lambda page: page.component("posts/index").etc())
    # The flash was consumed by the previous assertion's request already; a *fresh* request
    # right after the redirect (no intervening page load) is what actually carries it:
    redirect_response = await client.acting_as(user).post("/posts", json={"title": "Yet another"})
    next_page = await client.acting_as(user).inertia().get("/posts")
    next_page.assert_inertia(lambda page: page.has_flash("success", "Post created.").etc())
    assert redirect_response.status_code in (302, 303)


async def test_inertia_props_reads_a_value_by_dot_path(client: TestClient, user) -> None:
    await client.acting_as(user).post("/posts", json={"title": "Dotted props"})
    response = await client.inertia().get("/posts")
    assert response.inertia_props("posts.total") == 1
    props = response.inertia_props()
    assert "posts" in props


async def test_reload_only_and_reload_except(client: TestClient, user) -> None:
    await client.acting_as(user).post("/posts", json={"title": "Reload me"})
    response = await client.inertia().get("/posts")

    only = await response.reload_only("posts")
    only.assert_inertia(lambda page: page.has("posts").missing("notifications"))

    except_ = await response.reload_except("posts")
    except_.assert_inertia(lambda page: page.missing("posts").has("notifications").etc())


async def test_load_deferred_props(client: TestClient) -> None:
    response = await client.inertia().get("/posts")
    response.assert_inertia(lambda page: page.has_deferred("sidebar").etc())

    loaded = await response.load_deferred_props()
    loaded.assert_inertia(lambda page: page.has("sidebar"))

    loaded_group = await response.load_deferred_props("default")
    loaded_group.assert_inertia(lambda page: page.has("sidebar"))
