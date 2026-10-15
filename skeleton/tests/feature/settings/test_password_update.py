from fastogram.security import hash as hash_
from fastogram.testing import TestClient


async def test_password_screen_is_displayed(client: TestClient, user) -> None:
    response = await client.acting_as(user).get("/settings/security")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("settings/security"))


async def test_password_can_be_updated(client: TestClient, user) -> None:
    response = await client.acting_as(user).put(
        "/settings/password",
        json={
            "current_password": "password",
            "password": "new-password",
            "password_confirmation": "new-password",
        },
    )

    response.assert_redirect()
    # `User.find()` would return the Python object this test's db scope already cached from the
    # `user` fixture, unrefreshed; `.refresh()` forces a real reload (T-31).
    await user.refresh()
    assert hash_.check("new-password", user.password)


async def test_correct_password_must_be_provided_to_update_password(client: TestClient, user) -> None:
    response = await client.acting_as(user).from_url("/settings/security").put(
        "/settings/password",
        json={
            "current_password": "wrong-password",
            "password": "new-password",
            "password_confirmation": "new-password",
        },
    )

    response.assert_session_has_errors(["current_password"])
