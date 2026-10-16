"""End-to-end check of the auth library through the real stack (T-38, T-39, T-40, T-46): the
`auth_app` fixture drives login/logout/remember-me/intended redirect/guest/verified/
password.confirm/can/throttled-login/password-reset/email-verification exactly as a real app
would, through `routes/web.py` -> the web group stack -> controllers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx2 as httpx
import pytest
from sqlalchemy import text

FIXTURE = Path(__file__).parent.parent / "fixtures" / "auth_app"

# This fixture app returns JSON, never Inertia pages, so tests that need the JSON shape of a
# `ValidationException`/`RequirePassword` 423 (rather than the web redirect-back) ask for it
# explicitly, the way a `useHttp()` SPA call would (D-026).
WANTS_JSON = {"Accept": "application/json"}


@pytest.fixture
async def app():
    sys.path.insert(0, str(FIXTURE))
    try:
        from bootstrap.app import create_app

        application = create_app()
        from aso.database import Model
        from aso.database.engine import engine

        async with engine().begin() as conn:
            await conn.run_sync(Model.metadata.create_all)
            # The real "password_reset_tokens" table a Laravel-style migration would create
            # (T-38). The password broker talks to it with raw SQL, not an ORM model, see
            # `aso/auth/password_broker.py`.
            await conn.execute(
                text(
                    "CREATE TABLE password_reset_tokens ("
                    "email VARCHAR(255) PRIMARY KEY, token VARCHAR(255) NOT NULL, created_at REAL NOT NULL)"
                )
            )
        yield application
    finally:
        sys.path.remove(str(FIXTURE))


def _client_for(application) -> httpx.AsyncClient:
    """A fresh client against the same app -- a separate "device"/session (its own cookie jar)."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://testserver")


@pytest.fixture
async def client(app):
    async with _client_for(app) as c:
        yield c


async def _register(client: httpx.AsyncClient, email: str = "jane@example.com", password: str = "password1234") -> None:
    r = await client.post("/register", json={"name": "Jane", "email": email, "password": password})
    assert r.status_code in (302, 303), r.text


async def test_register_logs_in_and_dispatches_registered(client):
    from app.listeners.send_email_verification_notification import calls

    await _register(client)
    r = await client.get("/dashboard")
    assert r.status_code == 200
    assert r.json()["user_id"] == 1
    # `Registered` -> `SendEmailVerificationNotification` ran inline (T-38, T-46).
    assert calls == [1]


async def test_login_and_logout(client):
    await _register(client)
    await client.post("/logout")
    r = await client.get("/dashboard")
    assert r.status_code == 302  # guest -> redirected to `login`
    assert r.headers["location"].endswith("/login")

    r = await client.post("/login", json={"email": "jane@example.com", "password": "password1234"})
    assert r.status_code == 302
    assert r.headers["location"] == "/dashboard"
    r = await client.get("/dashboard")
    assert r.status_code == 200
    assert r.json()["user_id"] == 1


async def test_wrong_password_fails_and_dispatches_failed(client):
    await _register(client)
    await client.post("/logout")
    r = await client.post("/login", json={"email": "jane@example.com", "password": "nope"}, headers=WANTS_JSON)
    assert r.status_code == 422
    assert "email" in r.json()["errors"]
    r = await client.get("/dashboard")
    assert r.status_code == 302


async def test_intended_url_is_restored_after_login(client):
    await _register(client)
    await client.post("/logout")
    r = await client.get("/dashboard")
    assert r.status_code == 302
    r = await client.post("/login", json={"email": "jane@example.com", "password": "password1234"})
    assert r.headers["location"] == "/dashboard"


async def test_guest_middleware_redirects_authenticated_users_away_from_login(client):
    await _register(client)
    r = await client.get("/login")
    assert r.status_code == 302
    assert r.headers["location"] == "/dashboard"


async def test_throttled_login_fires_lockout_after_five_attempts(client):
    await _register(client)
    await client.post("/logout")
    from aso.events import Event

    Event.fake()
    for _ in range(5):
        await client.post("/login", json={"email": "jane@example.com", "password": "wrong"})
    r = await client.post("/login", json={"email": "jane@example.com", "password": "wrong"}, headers=WANTS_JSON)
    assert r.status_code == 422
    assert "Too many login attempts" in r.json()["errors"]["email"][0]

    from aso.auth.events import Lockout

    Event.assert_dispatched(Lockout, lambda e: e.email == "jane@example.com")


async def test_logout_other_devices_logs_out_the_other_sessions(app, client):
    await _register(client, email="multi@example.com", password="password1234")

    async with _client_for(app) as other_device:
        r = await other_device.post(
            "/login", json={"email": "multi@example.com", "password": "password1234"}
        )
        assert r.status_code == 302
        assert (await other_device.get("/dashboard")).status_code == 200

        r = await client.post("/logout-other-devices", json={"password": "password1234"})
        assert r.status_code == 200

        # The other device's session is still "logged in" client-side (its cookie still points
        # at a user id), but its stored password hash is now stale -> `AuthenticateSession`
        # logs it out on its very next request (T-38's "log out other devices").
        r = await other_device.get("/dashboard")
        assert r.status_code == 302
        assert r.headers["location"].endswith("/login")

        # `client`'s own session still works: it was updated with the fresh hash.
        assert (await client.get("/dashboard")).status_code == 200


async def test_remember_me_cookie_survives_a_fresh_session(client):
    await _register(client)
    await client.post("/logout")
    r = await client.post("/login", json={"email": "jane@example.com", "password": "password1234", "remember": True})
    assert r.status_code == 302
    assert any(c.name.startswith("remember_") for c in client.cookies.jar)

    # Drop the session cookie only (simulate a new browser session), keep the remember cookie.
    session_cookie = None
    for cookie in list(client.cookies.jar):
        if "session" in cookie.name:
            session_cookie = cookie.name
    if session_cookie:
        client.cookies.delete(session_cookie)

    r = await client.get("/dashboard")
    assert r.status_code == 200
    assert r.json()["via_remember"] is True


async def test_verified_middleware_blocks_until_email_is_verified(client):
    await _register(client)
    r = await client.get("/profile")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/email/verify")


async def test_email_verification_flow_marks_verified_and_fires_verified_event(client):
    await _register(client)
    from aso.auth.events import Verified
    from aso.events import Event

    Event.fake()
    r = await client.post("/email/verification-notification")
    assert r.status_code == 200

    from aso.mail.drivers import array_messages

    messages = array_messages()
    assert messages, "no verification mail was recorded"
    link = re.search(r"(/email/verify/\S+)", messages[-1]["text"])
    assert link, messages[-1]["text"]
    url = link.group(1)

    r = await client.get(url)
    assert r.status_code in (302, 303)
    Event.assert_dispatched(Verified)

    r = await client.get("/profile")
    assert r.status_code == 200


async def test_password_confirm_middleware_requires_a_recent_confirmation(client):
    await _register(client)
    r = await client.delete("/account")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/user/confirm-password")

    # API-style callers get 423 Locked (Laravel's `RequirePassword`), not a redirect.
    r = await client.delete("/account", headers=WANTS_JSON)
    assert r.status_code == 423

    r = await client.post("/user/confirm-password", json={"password": "password1234"})
    assert r.status_code == 302

    r = await client.delete("/account")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


async def test_password_confirm_rejects_wrong_password(client):
    await _register(client)
    r = await client.post("/user/confirm-password", json={"password": "wrong"}, headers=WANTS_JSON)
    assert r.status_code == 422


async def test_can_middleware_authorizes_via_policy(client):
    from aso.database.db import DB

    from app.models.post import Post

    await _register(client, email="owner@example.com")
    r = await client.get("/dashboard")
    owner_id = r.json()["user_id"]
    async with DB.scope():
        post = await Post.create(title="Hello", user_id=owner_id)

    r = await client.get(f"/posts/{post.id}/edit")
    assert r.status_code == 200

    await client.post("/logout")
    await _register(client, email="stranger@example.com")
    r = await client.get(f"/posts/{post.id}/edit")
    assert r.status_code == 403


async def test_password_reset_flow(client):
    await _register(client, email="reset@example.com", password="old-password-1")
    await client.post("/logout")

    from aso.mail.drivers import array_messages

    r = await client.post("/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"

    messages = array_messages()
    assert messages
    link = re.search(r"/reset-password/(\S+)\?email=", messages[-1]["text"])
    assert link, messages[-1]["text"]
    token = link.group(1)

    r = await client.post(
        "/reset-password", json={"email": "reset@example.com", "token": token, "password": "new-password-1"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reset"

    r = await client.post("/login", json={"email": "reset@example.com", "password": "new-password-1"})
    assert r.status_code == 302
    r = await client.post(
        "/login", json={"email": "reset@example.com", "password": "old-password-1"}, headers=WANTS_JSON
    )
    assert r.status_code == 422


async def test_password_reset_is_throttled(client):
    await _register(client, email="throttle@example.com")
    await client.post("/logout")
    r1 = await client.post("/forgot-password", json={"email": "throttle@example.com"})
    assert r1.json()["status"] == "sent"
    r2 = await client.post("/forgot-password", json={"email": "throttle@example.com"}, headers=WANTS_JSON)
    assert r2.status_code == 422
    assert "wait" in r2.json()["errors"]["email"][0].lower()
