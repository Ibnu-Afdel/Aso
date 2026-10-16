"""End-to-end `Request` API tests through the real stack (T-14)."""

from __future__ import annotations

import httpx2 as httpx


async def test_sync_inspection_methods(client: httpx.AsyncClient):
    client.cookies.set("flavor", "vanilla")
    r = await client.get(
        "/misc/inspect?q=abc",
        headers={"X-Custom": "val", "Accept": "application/json"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == "/misc/inspect"
    assert body["full_url"] == "http://testserver/misc/inspect?q=abc"
    assert body["method"] == "GET"
    assert body["header"] == "val"
    assert body["cookie"] == "vanilla"
    assert body["query"] == "abc"
    assert body["is_admin"] is False
    assert body["route_is"] is True
    assert body["expects_json"] is True
    assert body["is_inertia"] is False
    assert body["client_ip"] is not None


async def test_is_matches_wildcard_path_patterns(client: httpx.AsyncClient):
    r = await client.get("/admin/users")
    assert r.status_code == 200  # sanity: route exists
    r = await client.get("/misc/inspect")
    assert r.json()["is_admin"] is False


async def test_inertia_header_detection(client: httpx.AsyncClient):
    r = await client.get("/misc/inspect", headers={"X-Inertia": "true", "X-Inertia-Version": ""})
    assert r.json()["is_inertia"] is True


async def test_async_input_methods(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/inspect", json={"title": "T", "flag": "true"}, headers=xsrf)
    body = r.json()
    assert body["all"] == {"title": "T", "flag": "true"}
    assert body["input_title"] == "T"
    assert body["has_title"] is True
    assert body["boolean_flag"] is True
    assert body["only"] == {"title": "T"}
    assert body["except_"] == {"flag": "true"}


async def test_boolean_defaults_to_false_when_absent(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/inspect", json={}, headers=xsrf)
    assert r.json()["boolean_flag"] is False
    assert r.json()["has_title"] is False
    assert r.json()["input_title"] == "none"


async def test_file_upload(client: httpx.AsyncClient):
    r = await client.post("/misc/upload", files={"avatar": ("a.png", b"fake-bytes", "image/png")})
    assert r.status_code == 200
    assert r.json() == {"filename": "a.png", "content_type": "image/png"}


async def test_file_missing_returns_none(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/upload", data={}, headers=xsrf)
    assert r.json() == {"file": None}


async def test_body_readable_by_middleware_and_controller_via_shared_cache(client: httpx.AsyncClient, mw_state):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/body", json={"x": "shared"}, headers=xsrf)
    assert r.json() == {"x": "shared"}
    assert mw_state["peek"] == ["peek:shared"]


async def test_request_body_too_large_raises_413(client: httpx.AsyncClient):
    from aso.config import set_config

    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", ""), "Accept": "application/json"}
    set_config("app.max_buffered_body", 5)
    try:
        r = await client.post("/misc/body", json={"x": "a body much longer than five bytes"}, headers=xsrf)
        assert r.status_code == 413
        assert "max_buffered_body" in r.json()["message"]
    finally:
        set_config("app.max_buffered_body", 10 * 1024 * 1024)


async def test_request_body_too_large_is_enforced_for_controller_reads_too(client: httpx.AsyncClient):
    from aso.config import set_config

    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", ""), "Accept": "application/json"}
    set_config("app.max_buffered_body", 5)
    try:
        r = await client.post("/misc/inspect", json={"title": "a body much longer than five bytes"}, headers=xsrf)
        assert r.status_code == 413
    finally:
        set_config("app.max_buffered_body", 10 * 1024 * 1024)
