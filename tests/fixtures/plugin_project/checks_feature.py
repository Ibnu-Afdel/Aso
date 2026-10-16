"""Exercises `aso.testing.plugin`'s own fixtures end-to-end, as a real app's test suite
would use them (T-55). Run via a subprocess from `tests/testing/test_plugin_end_to_end.py`, not
collected by the main Aso suite (filename does not match its `python_files`).
"""

from __future__ import annotations

import pytest

from aso.testing import TestClient, assert_database_count


async def test_create_a_post(client: TestClient) -> None:
    response = await client.post("/posts")
    assert response.status_code == 200
    await assert_database_count("posts", 1)


async def test_the_previous_test_s_post_is_gone(client: TestClient) -> None:
    """Proves the autouse `db` fixture rolled the previous test's transaction back."""
    await assert_database_count("posts", 0)


@pytest.fixture
async def user():
    from app.models.user import User

    return await User.create(name="Jane", email="jane@example.com", password="secret1234")


async def test_acting_as_logs_in_for_the_next_request(client: TestClient, user) -> None:
    response = await client.acting_as(user).inertia().get("/posts")
    response.assert_ok()
    assert response.inertia_props("me") == user.id
    await client.assert_authenticated_as(user)


async def test_a_fresh_client_in_a_new_test_is_a_guest(client: TestClient) -> None:
    """Proves `client` gets a fresh cookie jar, and the array session store was cleared, even
    though the previous test logged a user in."""
    await client.assert_guest()
    response = await client.inertia().get("/posts")
    assert response.inertia_props("me") is None
