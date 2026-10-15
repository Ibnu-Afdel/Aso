from fastogram.testing import TestClient

from database.factories.user_factory import UserFactory


async def test_login_screen_can_be_rendered(client: TestClient) -> None:
    response = await client.get("/login")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/login"))


async def test_users_can_authenticate_using_the_login_screen(client: TestClient) -> None:
    user = await UserFactory.new().create(password="password")

    response = await client.post("/login", json={"email": user.email, "password": "password"})

    await client.assert_authenticated_as(user)
    response.assert_redirect_to_route("dashboard")


async def test_users_cannot_authenticate_with_invalid_password(client: TestClient) -> None:
    user = await UserFactory.new().create(password="password")

    response = await client.from_url("/login").post("/login", json={"email": user.email, "password": "wrong-password"})

    await client.assert_guest()
    response.assert_session_has_errors(["email"])


async def test_users_can_logout(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/logout")

    await client.assert_guest()
    response.assert_redirect("/")


async def test_login_is_rate_limited_after_too_many_attempts(client: TestClient) -> None:
    user = await UserFactory.new().create(password="password")

    for _ in range(5):
        await client.post("/login", json={"email": user.email, "password": "wrong-password"})

    response = await client.from_url("/login").post("/login", json={"email": user.email, "password": "wrong-password"})

    response.assert_session_has_errors({"email": "Too many login attempts."}, partial=True)
