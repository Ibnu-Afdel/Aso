"""T-19 "Errors in the page object" + T-18 "How flash reaches React"."""

from __future__ import annotations

from conftest import INERTIA

from fastogram.config import set_config


async def _post_invalid_title(client, xsrf):
    return await client.post(
        "/errors",
        json={"title": "ab"},
        headers={**INERTIA, **xsrf, "Referer": "http://testserver/errors/create"},
    )


async def test_default_bag_with_no_error_bag_header_is_unwrapped(client):
    await client.get("/errors/create")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    await _post_invalid_title(client, xsrf)
    r = await client.get("/errors/create", headers=INERTIA)
    assert r.json()["props"]["errors"] == {"title": "The title field must be at least 3 characters."}


async def test_default_bag_with_error_bag_header_nests_under_that_name(client):
    await client.get("/errors/create")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    await _post_invalid_title(client, xsrf)
    r = await client.get("/errors/create", headers={**INERTIA, "X-Inertia-Error-Bag": "custom"})
    assert r.json()["props"]["errors"] == {"custom": {"title": "The title field must be at least 3 characters."}}


async def test_named_error_bag_from_the_form_requests_class_attribute(client):
    await client.get("/errors/create")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    await client.post(
        "/errors/invite",
        json={"email": "not-an-email"},
        headers={**INERTIA, **xsrf, "Referer": "http://testserver/errors/create"},
    )
    r = await client.get("/errors/create", headers=INERTIA)
    errors = r.json()["props"]["errors"]
    assert "invite" in errors
    assert "email" in errors["invite"]


async def test_no_errors_gives_an_empty_object(client):
    r = await client.get("/errors/create", headers=INERTIA)
    assert r.json()["props"]["errors"] == {}


async def test_all_errors_config_sends_every_message_per_field(client):
    set_config("inertia.all_errors", True)
    try:
        await client.get("/errors/create")
        xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
        await _post_invalid_title(client, xsrf)
        r = await client.get("/errors/create", headers=INERTIA)
        errors = r.json()["props"]["errors"]
        assert isinstance(errors["title"], list)
    finally:
        set_config("inertia.all_errors", False)


async def test_flash_set_directly_on_the_response_appears_immediately(client):
    r = await client.get("/flash-now", headers=INERTIA)
    assert r.json()["flash"] == {"success": "Saved."}


async def test_flash_is_not_shown_again_on_the_next_request(client):
    await client.get("/flash-now", headers=INERTIA)
    r = await client.get("/shared", headers=INERTIA)
    assert "flash" not in r.json() or r.json().get("flash") == {}


async def test_prefetch_requests_get_no_flash_and_do_not_age_it(client):
    r = await client.get("/flash-now", headers={**INERTIA, "Purpose": "prefetch"})
    assert "flash" not in r.json()
    # since the prefetch skipped ageing, a real follow-up visit still sees the flash
    r = await client.get("/shared", headers=INERTIA)
    assert r.json().get("flash") == {"success": "Saved."}
