from aso.testing import TestClient
from aso.testing.database import assert_database_has


async def test_registration_screen_can_be_rendered(client: TestClient) -> None:
    response = await client.get("/register")
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("auth/register"))


async def test_new_users_can_register(client: TestClient) -> None:
    response = await client.post(
        "/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password",
            "password_confirmation": "password",
        },
    )

    await client.assert_authenticated()
    response.assert_redirect_to_route("dashboard")
    await assert_database_has("users", {"email": "test@example.com"})


async def test_registration_requires_a_unique_email(client: TestClient, user) -> None:
    response = await client.from_url("/register").post(
        "/register",
        json={
            "name": "Test User",
            "email": user.email,
            "password": "password",
            "password_confirmation": "password",
        },
    )

    response.assert_session_has_errors(["email"])
