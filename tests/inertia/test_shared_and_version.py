"""T-17 shared data + asset versioning, and T-16 dot-key expansion / sharedProps."""

from __future__ import annotations

from conftest import INERTIA


async def test_shared_props_are_merged_with_dot_keys_expanded(client):
    r = await client.get("/shared", headers=INERTIA)
    props = r.json()["props"]
    assert props["name"] == "InertiaApp"
    assert props["auth"]["user"] == {"id": 1, "name": "Ada"}  # "auth.user" expands to nested dict
    assert props["countries"] == ["US", "NL"]  # share_once wrapped in once()
    assert props["feature_flag"] is True  # share() called from another middleware


async def test_share_once_appears_in_once_props_metadata(client):
    r = await client.get("/shared", headers=INERTIA)
    once_props = r.json()["onceProps"]
    assert once_props["countries"] == {"prop": "countries", "expiresAt": None}


async def test_version_defaults_to_empty_string_without_a_build(client):
    r = await client.get("/shared", headers=INERTIA)
    assert r.json()["version"] == ""


async def test_stale_version_on_get_returns_409_with_location_and_current_version(client):
    r = await client.get("/shared", headers={"X-Inertia": "true", "X-Inertia-Version": "stale"})
    assert r.status_code == 409
    assert r.headers["x-inertia-location"] == "http://testserver/shared"
    assert r.headers["x-inertia-version"] == ""
    assert r.headers["vary"] == "X-Inertia"


async def test_vary_header_is_present_on_every_response(client):
    html_response = await client.get("/shared")
    assert html_response.headers["vary"] == "X-Inertia"
    json_response = await client.get("/shared", headers=INERTIA)
    assert json_response.headers["vary"] == "X-Inertia"


async def test_redirect_after_patch_becomes_303(client):
    await client.get("/errors/create")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.patch(
        "/errors",
        json={"title": "A valid title"},
        headers={**INERTIA, **xsrf, "Referer": "http://testserver/errors/create"},
        follow_redirects=False,
    )
    assert r.status_code == 303


async def test_redirect_after_post_stays_302(client):
    await client.get("/errors/create")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post(
        "/errors",
        json={"title": "A valid title"},
        headers={**INERTIA, **xsrf, "Referer": "http://testserver/errors/create"},
        follow_redirects=False,
    )
    assert r.status_code == 302
