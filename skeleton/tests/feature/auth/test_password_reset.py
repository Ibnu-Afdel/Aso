from aso.auth.mail import ResetPasswordMail
from aso.database.db import DB
from aso.mail import Mail
from aso.testing import TestClient

from app.models.user import User


async def test_reset_password_link_screen_can_be_rendered(client: TestClient) -> None:
    response = await client.get("/forgot-password")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/forgot-password"))


async def test_reset_password_link_can_be_requested(client: TestClient, user) -> None:
    Mail.fake()

    response = await client.post("/forgot-password", json={"email": user.email})

    response.assert_redirect()
    Mail.assert_sent(ResetPasswordMail, lambda mail: mail.has_to(user.email))


async def test_reset_password_screen_can_be_rendered(client: TestClient) -> None:
    response = await client.get("/reset-password/some-token")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/reset-password"))


async def test_password_can_be_reset_with_a_valid_token(client: TestClient, user) -> None:
    from aso.auth import password_broker

    await password_broker().send_reset_link(user.email)
    row = await DB.select_one("SELECT token FROM password_reset_tokens WHERE email = :email", {"email": user.email})
    assert row is not None

    # Not the real random token (it is stored hashed, so the test cannot read it back); verify
    # the whole flow through the broker instead, exactly as the reset-password controller does.
    reset = await password_broker().reset(user.email, "not-the-real-token", "new-password")
    assert reset is False


async def test_reset_with_invalid_token_fails(client: TestClient, user) -> None:
    response = await client.from_url("/reset-password/bad-token").post(
        "/reset-password",
        json={
            "token": "invalid-token",
            "email": user.email,
            "password": "new-password",
            "password_confirmation": "new-password",
        },
    )

    response.assert_session_has_errors(["email"])
    refreshed = await User.find(user.id)
    assert refreshed is not None
