"""End-to-end tests for method spoofing (T-10 "How it works", T-11 open question 3)."""

from __future__ import annotations

import httpx2 as httpx


async def _xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    await client.get("/misc/ping")
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


async def test_method_spoofing_via_method_field_put_patch_delete(client: httpx.AsyncClient):
    headers = await _xsrf(client)
    for verb in ("PUT", "PATCH", "DELETE"):
        r = await client.post("/misc/echo", data={"_method": verb}, headers=headers)
        assert r.json() == {"method": verb}, verb


async def test_method_spoofing_via_x_http_method_override_header(client: httpx.AsyncClient):
    headers = await _xsrf(client)
    r = await client.post("/misc/echo", headers={**headers, "X-HTTP-Method-Override": "patch"})
    assert r.json() == {"method": "PATCH"}


async def test_only_put_patch_delete_are_allowed_overrides(client: httpx.AsyncClient):
    headers = await _xsrf(client)
    for bogus in ("GET", "HEAD", "OPTIONS", "TRACE"):
        r = await client.post("/misc/echo", data={"_method": bogus}, headers=headers)
        assert r.json() == {"method": "POST"}, bogus


async def test_method_spoofing_is_not_applied_under_the_api_prefix(client: httpx.AsyncClient):
    """`/api/misc/echo` only has GET and PUT registered (no POST): if spoofing wrongly rewrote
    this POST to PUT, it would succeed; instead it must 404 as a plain, un-spoofed POST."""
    r = await client.post("/api/misc/echo", data={"_method": "PUT"})
    assert r.status_code == 404
