"""T-20's built-in exception -> response conversions table, for web (Inertia) and API/JSON."""

from __future__ import annotations

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


# ---------------------------------------------------------------- AuthorizationException


async def test_authorization_exception_is_403_on_inertia(client):
    r = await client.get("/authz", headers=INERTIA)
    assert r.status_code == 403
    page = r.json()
    assert page["component"] == "error"
    assert page["props"]["status"] == 403
    assert page["props"]["message"] == "You may not view this invoice."


async def test_authorization_exception_is_403_json_on_api_group(client):
    r = await client.get("/api/authz")
    assert r.status_code == 403
    assert r.json() == {"message": "You may not view this invoice."}


# ---------------------------------------------------------------- AuthenticationException


async def test_authentication_exception_redirects_to_configured_guest_target(client):
    r = await client.get("/authn")
    assert r.status_code == 302
    assert r.headers["location"] == "/login"  # from m.redirect_guests_to("/login")


async def test_authentication_exception_honours_its_own_redirect_to(client):
    r = await client.get("/authn-custom")
    assert r.status_code == 302
    assert r.headers["location"] == "/custom-login"


async def test_authentication_exception_api_401_json_with_redirect_to(client):
    r = await client.get("/api/authn")
    assert r.status_code == 401
    body = r.json()
    assert body["message"] == "Unauthenticated."
    assert body["redirect_to"] == "/login"


# ---------------------------------------------------------------- ThrottleRequestsException


async def test_throttle_exception_429_with_retry_after_web(client):
    r = await client.get("/throttle", headers=INERTIA)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "30"
    assert r.json()["props"]["status"] == 429


async def test_throttle_exception_429_with_retry_after_api(client):
    r = await client.get("/api/throttle")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "30"
    assert r.json()["message"] == "Too Many Attempts."


# ---------------------------------------------------------------- ModelNotFound


async def test_model_not_found_is_404_on_inertia(client):
    r = await client.get("/model-missing", headers=INERTIA)
    assert r.status_code == 404
    page = r.json()
    assert page["component"] == "error"
    assert page["props"]["message"] == "No query results for model [Invoice] 42."


async def test_model_not_found_is_404_json_on_api_group(client):
    r = await client.get("/api/model-missing")
    assert r.status_code == 404
    assert r.json() == {"message": "No query results for model [Invoice] 42."}


# ---------------------------------------------------------------- ValidationException


async def test_validation_exception_redirects_back_and_flashes_errors_and_old_input(client):
    await client.get("/home", headers={**INERTIA, "Referer": "http://testserver/home"})
    r = await client.post(
        "/validation",
        json={"title": "a", "quantity": -1},
        headers={**INERTIA, "Referer": "http://testserver/home"},
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/home"
    r = await client.get("/home", headers=INERTIA)
    page = r.json()
    assert page["props"]["errors"] == {
        "title": "The title field must be at least 3 characters.",
        "quantity": "The quantity field must be greater than 0.",
    }


async def test_validation_exception_put_uses_303(client):
    r = await client.put(
        "/validation", json={"title": "a", "quantity": -1}, headers={**INERTIA, "Referer": "http://testserver/home"}
    )
    assert r.status_code == 303


async def test_validation_exception_api_422_laravel_shape(client):
    r = await client.post("/api/validation", json={"title": "a", "quantity": -1})
    assert r.status_code == 422
    body = r.json()
    assert body["message"].endswith("(and 1 more error)")
    assert set(body["errors"].keys()) == {"title", "quantity"}
    assert body["errors"]["title"] == ["The title field must be at least 3 characters."]
    assert body["errors"]["quantity"] == ["The quantity field must be greater than 0."]


# ---------------------------------------------------------------- plain 500


async def test_unhandled_exception_is_500(client):
    r = await client.get("/boom", headers=INERTIA)
    assert r.status_code == 500
    page = r.json()
    assert page["component"] == "error"
    assert page["props"] == {"app_name": "ErrorsApp", "status": 500, "errors": {}}  # no message leaked


async def test_unhandled_exception_api_hides_message_in_production(client):
    r = await client.get("/boom", headers={"Accept": "application/json"})
    assert r.status_code == 500
    assert r.json() == {"message": "Server Error."}
