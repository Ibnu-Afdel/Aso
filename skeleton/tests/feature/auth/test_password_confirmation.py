from fastogram.testing import TestClient


async def test_confirm_password_screen_can_be_rendered(client: TestClient, user) -> None:
    response = await client.acting_as(user).get("/user/confirm-password")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/confirm-password"))


async def test_password_can_be_confirmed(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/user/confirm-password", json={"password": "password"})
    response.assert_redirect()
    response.assert_session_has_no_errors()


async def test_password_is_not_confirmed_with_invalid_password(client: TestClient, user) -> None:
    response = await client.acting_as(user).from_url("/user/confirm-password").post(
        "/user/confirm-password", json={"password": "wrong-password"}
    )
    response.assert_session_has_errors(["password"])
