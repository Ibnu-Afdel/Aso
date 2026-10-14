"""T-16 history encryption, `location()`, and `PageNotFound`."""

from __future__ import annotations

from conftest import INERTIA

from fastogram.config import set_config


async def test_encrypt_history_on_the_response_sets_the_flag(client):
    r = await client.get("/transactions", headers=INERTIA)
    assert r.json()["encryptHistory"] is True


async def test_pages_without_encrypt_history_omit_the_flag(client):
    r = await client.get("/shared", headers=INERTIA)
    assert "encryptHistory" not in r.json()


async def test_config_encrypt_history_applies_to_every_page(client):
    set_config("inertia.encrypt_history", True)
    try:
        r = await client.get("/shared", headers=INERTIA)
        assert r.json()["encryptHistory"] is True
    finally:
        set_config("inertia.encrypt_history", False)


async def test_location_on_an_inertia_request_is_409_with_x_inertia_location(client):
    r = await client.get("/go", headers=INERTIA)
    assert r.status_code == 409
    assert r.headers["x-inertia-location"] == "https://example.com/external"


async def test_location_on_a_plain_request_is_a_302_redirect(client):
    r = await client.get("/go", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/external"


async def test_missing_page_file_raises_page_not_found(client):
    r = await client.get("/missing-page", headers=INERTIA)
    assert r.status_code == 500
