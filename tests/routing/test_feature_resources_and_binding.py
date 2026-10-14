"""End-to-end routing tests (T-10): resource CRUD, route-model binding, `.where*()` constraints,
optional parameters, and resource edge cases (`api_resource`, skipped missing actions)."""

from __future__ import annotations

import httpx2 as httpx


def _xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


async def _create_post(client: httpx.AsyncClient, title: str = "Hello world", slug: str = "hello-world") -> str:
    await client.get("/misc/ping")
    r = await client.post("/posts", json={"title": title, "slug": slug}, headers=_xsrf(client))
    assert r.status_code == 302, r.text
    return r.headers["location"]


# ---------------------------------------------------------------- resource CRUD


async def test_resource_index_create_store_show(client: httpx.AsyncClient):
    assert (await client.get("/posts")).json() == {"posts": []}
    assert (await client.get("/posts/create")).status_code == 200
    location = await _create_post(client)
    assert location == "/posts/1"
    r = await client.get(location)
    assert r.json()["post"]["title"] == "Hello world"


async def test_resource_update_accepts_put_and_patch(client: httpx.AsyncClient):
    location = await _create_post(client)
    r = await client.put(location, json={"title": "Updated via PUT"}, headers=_xsrf(client))
    assert r.status_code == 302
    assert (await client.get(location)).json()["post"]["title"] == "Updated via PUT"

    r = await client.patch(location, json={"title": "Updated via PATCH"}, headers=_xsrf(client))
    assert r.status_code == 302
    assert (await client.get(location)).json()["post"]["title"] == "Updated via PATCH"


async def test_resource_destroy(client: httpx.AsyncClient):
    location = await _create_post(client)
    r = await client.delete(location, headers=_xsrf(client))
    assert r.status_code == 302
    assert (await client.get(location)).status_code == 404


async def test_resource_show_404_for_missing_model(client: httpx.AsyncClient):
    r = await client.get("/posts/999")
    assert r.status_code == 404


async def test_route_model_binding_by_column(client: httpx.AsyncClient):
    await _create_post(client, slug="by-slug-test")
    r = await client.get("/posts-by-slug/by-slug-test")
    assert r.status_code == 200
    assert r.json()["post"]["slug"] == "by-slug-test"
    assert (await client.get("/posts-by-slug/does-not-exist")).status_code == 404


# ---------------------------------------------------------------- nested / scoped binding


async def test_nested_resource_scoped_binding(client: httpx.AsyncClient):
    post_location = await _create_post(client)
    r = await client.post(f"{post_location}/comments", json={"body": "nice post"}, headers=_xsrf(client))
    assert r.status_code == 200
    comment_id = r.json()["id"]

    r = await client.get(f"{post_location}/comments/{comment_id}")
    assert r.status_code == 200
    assert r.json()["comment"]["body"] == "nice post"


async def test_nested_resource_binding_404_when_comment_belongs_to_a_different_post(client: httpx.AsyncClient):
    post_a = await _create_post(client, title="Post A title", slug="post-a")
    post_b = await _create_post(client, title="Post B title", slug="post-b")
    r = await client.post(f"{post_a}/comments", json={"body": "on A"}, headers=_xsrf(client))
    comment_id = r.json()["id"]
    # the comment belongs to post A: looking it up scoped under post B must 404.
    r = await client.get(f"{post_b}/comments/{comment_id}")
    assert r.status_code == 404


# ---------------------------------------------------------------- wheres / type convertors


async def test_where_number_mismatch_is_404(client: httpx.AsyncClient):
    assert (await client.get("/misc/orders/not-a-number")).status_code == 404
    assert (await client.get("/misc/orders/42")).status_code == 200


async def test_where_alpha_mismatch_is_404(client: httpx.AsyncClient):
    assert (await client.get("/misc/tags/abc123")).status_code == 404
    assert (await client.get("/misc/tags/abc")).status_code == 200


async def test_where_uuid_mismatch_is_404_not_422(client: httpx.AsyncClient):
    assert (await client.get("/misc/files/not-a-uuid")).status_code == 404
    r = await client.get("/misc/files/12345678-1234-5678-1234-567812345678")
    assert r.status_code == 200
    assert r.json()["uuid"] == "12345678-1234-5678-1234-567812345678"


async def test_where_custom_pattern_allows_slashes(client: httpx.AsyncClient):
    r = await client.get("/misc/docs/a/b/c")
    assert r.status_code == 200
    assert r.json()["path"] == "a/b/c"


async def test_int_typed_path_param_404_on_malformed_value_not_422(client: httpx.AsyncClient):
    """A non-integer segment for an `int`-annotated parameter does not match the route at all
    (404), rather than matching and then failing FastAPI validation (422), per T-10."""
    assert (await client.get("/misc/users/abc/posts/1")).status_code == 404
    assert (await client.get("/misc/users/1/posts/abc")).status_code == 404
    r = await client.get("/misc/users/1/posts/2")
    assert r.status_code == 200
    assert r.json() == {"user_id": 1, "post_id": 2}


# ---------------------------------------------------------------- optional parameters


async def test_optional_parameter_present_and_absent(client: httpx.AsyncClient):
    assert (await client.get("/misc/archive/2020")).json() == {"year": 2020}
    assert (await client.get("/misc/archive")).json() == {"year": None}


# ---------------------------------------------------------------- resource edge cases


async def test_api_resource_excludes_create_and_edit_even_when_defined(client: httpx.AsyncClient):
    assert (await client.get("/api/widgets")).status_code == 200
    assert (await client.get("/api/widgets/create")).status_code == 404
    assert (await client.get("/api/widgets/1/edit")).status_code == 404
    assert (await client.get("/api/widgets/1")).json() == {"widget": 1}


async def test_resource_skips_actions_the_controller_never_defined(client: httpx.AsyncClient):
    """`ArchiveController` defines only `index`/`show`: the other five verbs must 404."""
    assert (await client.get("/api/archives")).status_code == 200
    assert (await client.get("/api/archives/1")).status_code == 200
    assert (await client.get("/api/archives/create")).status_code == 404
    assert (await client.put("/api/archives/1", json={})).status_code == 404
    assert (await client.delete("/api/archives/1")).status_code == 404
