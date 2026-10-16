"""End-to-end check of the spine: the S-1 loop through the real middleware stack."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx2 as httpx
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "blog"


@pytest.fixture
async def client():
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        app = create_app()
        from aso.database import Model
        from aso.database.engine import engine

        async with engine().begin() as conn:
            await conn.run_sync(Model.metadata.create_all)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        sys.path.remove(str(FIXTURE))


def page_from_html(html: str) -> dict:
    m = re.search(r'<script data-page="app" type="application/json">(.*?)</script>', html)
    assert m, html
    return json.loads(m.group(1))


def xsrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}


INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


async def test_first_visit_renders_html_page_object(client):
    r = await client.get("/posts/create")
    assert r.status_code == 200
    assert "\\/posts\\/create" in r.text
    page = page_from_html(r.text)
    assert page["component"] == "posts/create"
    assert page["props"] == {"name": "Blog", "errors": {}}
    assert "XSRF-TOKEN" in client.cookies


async def test_validation_redirects_back_with_errors_then_flash(client):
    await client.get("/posts/create")
    r = await client.post(
        "/posts", json={"title": "ab"}, headers={**INERTIA, **xsrf(client), "Referer": "http://testserver/posts/create"}
    )
    assert r.status_code == 302 and r.headers["location"] == "/posts/create"
    r = await client.get("/posts/create", headers=INERTIA)
    assert r.json()["props"]["errors"] == {"title": "The title field must be at least 3 characters."}

    r = await client.post("/posts", json={"title": "Hello world"}, headers={**INERTIA, **xsrf(client)})
    assert r.status_code == 302 and r.headers["location"] == "/posts"
    r = await client.get("/posts", headers=INERTIA)
    page = r.json()
    assert page["flash"] == {"success": "Post created."}
    assert page["props"]["errors"] == {}
    assert page["deferredProps"] == {"default": ["posts"]}
    r = await client.get(
        "/posts", headers={**INERTIA, "X-Inertia-Partial-Component": "posts/index", "X-Inertia-Partial-Data": "posts"}
    )
    assert [p["title"] for p in r.json()["props"]["posts"]] == ["Hello world"]
    assert "flash" not in r.json()


async def test_csrf_mismatch_on_inertia_redirects_back_with_flash(client):
    await client.get("/posts/create")
    # CSRF is off while APP_ENV=testing (T-12); force it on for this request.
    from aso.config import set_config

    set_config("app.environment", "local")
    r = await client.post("/posts", json={"title": "x"}, headers={**INERTIA, "Referer": "http://testserver/posts/create"})
    set_config("app.environment", "testing")
    assert r.status_code == 302
    r = await client.get("/posts/create", headers=INERTIA)
    assert r.json()["flash"] == {"error": "The page expired, please try again."}


async def test_version_mismatch_409_and_flash_survives(client):
    await client.get("/posts/create")
    await client.post("/posts", json={"title": "Hello"}, headers={**INERTIA, **xsrf(client)})
    r = await client.get("/posts", headers={"X-Inertia": "true", "X-Inertia-Version": "old"})
    assert r.status_code == 409
    assert r.headers["x-inertia-location"] == "http://testserver/posts"
    r = await client.get("/posts")
    assert page_from_html(r.text)["flash"] == {"success": "Post created."}


async def test_web_404_and_500_go_through_the_web_stack(client):
    r = await client.get("/nope", headers=INERTIA)
    assert r.status_code == 404
    assert r.json()["component"] == "error"
    assert r.json()["props"]["status"] == 404
    r = await client.get("/boom", headers=INERTIA)
    assert r.status_code == 500
    assert r.json()["props"] == {"name": "Blog", "status": 500, "errors": {}}


async def test_api_routes_are_stateless_json(client):
    r = await client.get("/api/posts/999")
    assert r.status_code == 404
    assert r.json() == {"message": "No query results for model [Post] 999."}
    assert "set-cookie" not in r.headers
    r = await client.get("/api/unknown")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


async def test_health_and_dict_responses(client):
    assert (await client.get("/up")).json() == {"status": "up"}
    assert (await client.get("/stats")).json() == {"count": 0}
