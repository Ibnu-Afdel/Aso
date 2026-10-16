from aso.testing import TestClient

from app.models.user import User


async def test_profile_page_is_displayed(client: TestClient, user) -> None:
    response = await client.acting_as(user).get("/settings/profile")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("settings/profile"))


async def test_profile_information_can_be_updated(client: TestClient, user) -> None:
    response = await client.acting_as(user).patch(
        "/settings/profile", json={"name": "New Name", "email": "new-email@example.com"}
    )

    response.assert_redirect_to_route("profile.edit")
    # `User.find()` would return the Python object this test's db scope already cached from the
    # `user` fixture, unrefreshed; `.refresh()` forces a real reload (T-31).
    await user.refresh()
    assert user.name == "New Name"
    assert user.email == "new-email@example.com"
    assert user.email_verified_at is None


async def test_email_verification_status_is_unchanged_when_email_address_is_unchanged(
    client: TestClient, user
) -> None:
    await client.acting_as(user).patch("/settings/profile", json={"name": "New Name", "email": user.email})

    await user.refresh()
    assert user.email_verified_at is not None


async def test_user_can_delete_their_account(client: TestClient, user) -> None:
    import time

    response = await (
        client.acting_as(user)
        .with_session({"auth.password_confirmed_at": time.time()})
        .from_url("/settings/profile")
        .delete("/settings/profile", json={"password": "password"})
    )

    await client.assert_guest()
    response.assert_redirect("/")
    assert await User.find(user.id) is None


async def test_correct_password_must_be_provided_to_delete_account(client: TestClient, user) -> None:
    import time

    response = await (
        client.acting_as(user)
        .with_session({"auth.password_confirmed_at": time.time()})
        .from_url("/settings/profile")
        .delete("/settings/profile", json={"password": "wrong-password"})
    )

    response.assert_session_has_errors(["password"])
    assert await User.find(user.id) is not None
