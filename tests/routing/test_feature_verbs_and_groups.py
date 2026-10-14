"""End-to-end routing tests through the real stack (T-10): verbs, redirects, named routes,
`route()`, groups, controller groups, `Route.include`, and a plain FastAPI router."""

from __future__ import annotations

import httpx2 as httpx


async def test_every_verb_reaches_the_controller(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    assert (await client.get("/misc/echo")).json() == {"method": "GET"}
    assert (await client.post("/misc/echo", headers=xsrf)).json() == {"method": "POST"}
    assert (await client.put("/misc/echo", headers=xsrf)).json() == {"method": "PUT"}
    assert (await client.patch("/misc/echo", headers=xsrf)).json() == {"method": "PATCH"}
    assert (await client.delete("/misc/echo", headers=xsrf)).json() == {"method": "DELETE"}
    assert (await client.options("/misc/echo", headers=xsrf)).status_code == 200


async def test_match_accepts_only_the_listed_methods(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    assert (await client.get("/misc/search?q=x")).json() == {"q": "x"}
    assert (await client.post("/misc/search", headers=xsrf)).status_code == 200
    assert (await client.put("/misc/search", headers=xsrf)).status_code == 404


async def test_any_accepts_every_method(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    for verb in ("get", "post", "put", "patch", "delete"):
        r = await client.request(verb.upper(), "/misc/any", headers=xsrf)
        assert r.status_code == 200, verb


async def test_redirect_default_status_is_302(client: httpx.AsyncClient):
    r = await client.get("/misc/home-old")
    assert r.status_code == 302
    assert r.headers["location"] == "/misc/ping"


async def test_redirect_with_explicit_status(client: httpx.AsyncClient):
    r = await client.get("/misc/old-blog")
    assert r.status_code == 301


async def test_permanent_redirect_is_301(client: httpx.AsyncClient):
    r = await client.get("/misc/legacy")
    assert r.status_code == 301
    assert r.headers["location"] == "/misc/ping"


async def test_route_inertia_renders_a_page(client: httpx.AsyncClient):
    r = await client.get("/misc/about", headers={"X-Inertia": "true", "X-Inertia-Version": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["component"] == "about"
    assert body["props"]["updated"] == "2026-10-01"


async def test_single_action_invokable_controller(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/invoke/5", headers=xsrf)
    assert r.status_code == 200
    assert r.json() == {"invoked": 5}
    assert (await client.post("/invoke/not-a-number", headers=xsrf)).status_code == 404


# ---------------------------------------------------------------- groups


async def test_prefix_name_and_middleware_group_nesting(client: httpx.AsyncClient):
    r = await client.get("/admin/users")
    assert r.status_code == 200
    assert r.json() == {"route": "admin.users.index"}

    r = await client.get("/admin/reports/sales")
    assert r.status_code == 200


async def test_controller_group_with_bare_string_actions(client: httpx.AsyncClient):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    assert (await client.get("/orders/9")).json() == {"id": 9}
    assert (await client.post("/orders", headers=xsrf)).json() == {"stored": True}


async def test_include_inherits_the_surrounding_group(client: httpx.AsyncClient):
    """`routes/included.py` is `Route.include()`d from inside the `admin` prefix/middleware
    group, so it must end up at `/admin/included`, named `admin.included`, carrying `mw_a`."""
    r = await client.get("/admin/included")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_plain_fastapi_router_is_mounted(client: httpx.AsyncClient):
    r = await client.get("/legacy/items")
    assert r.status_code == 200
    assert r.json() == []


async def test_unmatched_url_hits_the_fallback_through_the_web_stack(client: httpx.AsyncClient):
    r = await client.get("/this-does-not-exist")
    assert r.status_code == 404
    assert r.json()["fallback"] is True
    assert r.json()["path"] == "/this-does-not-exist"
