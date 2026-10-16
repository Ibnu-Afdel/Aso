"""End-to-end tests (T-10, T-11, T-21): signed URLs + the `signed` alias, `url()` helpers,
method spoofing, and `route:list` rows."""

from __future__ import annotations

from datetime import timedelta

import httpx2 as httpx

from aso.routing import url
from aso.routing.registry import route_list


async def test_signed_route_accepts_a_valid_signature(client: httpx.AsyncClient):
    signed = url().signed_route("misc.secret", {"id": 5})
    r = await client.get(signed.replace("http://testserver", ""))
    assert r.status_code == 200
    assert r.json() == {"id": 5}


async def test_signed_route_rejects_a_tampered_signature(client: httpx.AsyncClient):
    signed = url().signed_route("misc.secret", {"id": 5})
    r = await client.get(signed.replace("http://testserver", "") + "tampered")
    assert r.status_code == 403


async def test_signed_route_rejects_a_missing_signature(client: httpx.AsyncClient):
    r = await client.get("/misc/secret/5")
    assert r.status_code == 403


async def test_temporary_signed_route_rejects_an_expired_link(client: httpx.AsyncClient):
    expired = url().temporary_signed_route("misc.secret", timedelta(seconds=-5), params={"id": 5})
    r = await client.get(expired.replace("http://testserver", ""))
    assert r.status_code == 403


async def test_temporary_signed_route_accepts_an_unexpired_link(client: httpx.AsyncClient):
    valid = url().temporary_signed_route("misc.secret", timedelta(hours=1), params={"id": 5})
    r = await client.get(valid.replace("http://testserver", ""))
    assert r.status_code == 200


async def test_url_helpers_through_a_real_request(client: httpx.AsyncClient):
    r = await client.get("/misc/url")
    assert r.status_code == 200
    body = r.json()
    assert body["plain"] == "http://testserver/misc/ping"
    assert body["current"] == "http://testserver/misc/url"


# ---------------------------------------------------------------- method spoofing


async def test_method_spoofing_via_form_field(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/echo", data={"_method": "PUT"}, headers=xsrf)
    assert r.json() == {"method": "PUT"}
    r = await client.post("/misc/echo", data={"_method": "DELETE"}, headers=xsrf)
    assert r.json() == {"method": "DELETE"}
    r = await client.post("/misc/echo", data={"_method": "PATCH"}, headers=xsrf)
    assert r.json() == {"method": "PATCH"}


async def test_method_spoofing_via_header(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/echo", headers={**xsrf, "X-HTTP-Method-Override": "DELETE"})
    assert r.json() == {"method": "DELETE"}


async def test_method_spoofing_only_allows_put_patch_delete(client: httpx.AsyncClient):
    """Something other than PUT/PATCH/DELETE in `_method` must not change the verb."""
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/echo", data={"_method": "GET"}, headers=xsrf)
    assert r.json() == {"method": "POST"}


async def test_method_spoofing_does_not_apply_under_api(client: httpx.AsyncClient):
    """`routes/api.py` only registers GET and PUT for `/misc/echo`; if spoofing wrongly applied
    under `/api`, this POST would be rewritten to PUT and succeed instead of 404ing."""
    r = await client.post("/api/misc/echo", data={"_method": "PUT"})
    assert r.status_code == 404


# ---------------------------------------------------------------- route:list


async def test_route_list_rows_for_a_known_route(client: httpx.AsyncClient):
    rows = route_list()
    row = next(r for r in rows if r["name"] == "posts.show")
    assert row["method"] == "GET|HEAD"
    assert row["uri"] == "/posts/{post}"
    assert "PostController" in row["action"]
    assert row["group"] == "web"

    secret_row = next(r for r in rows if r["name"] == "misc.secret")
    assert secret_row["middleware"] == ["signed"]
