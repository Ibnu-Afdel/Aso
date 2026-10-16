"""T-57: `assert_database_has/missing/count`, `assert_model_exists/missing`, `seed()`."""

from __future__ import annotations

import pytest

from aso.testing import (
    assert_database_count,
    assert_database_has,
    assert_database_missing,
    assert_model_exists,
    assert_model_missing,
)
from aso.testing.client import TestClient


async def test_assert_database_has_and_missing_after_a_request(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/posts", json={"title": "Persisted via request"})
    response.assert_redirect()

    await assert_database_has("posts", {"title": "Persisted via request", "user_id": user.id})
    await assert_database_missing("posts", {"title": "Some other title"})


async def test_assert_database_count(client: TestClient, user) -> None:
    await assert_database_count("posts", 0)
    await client.acting_as(user).post("/posts", json={"title": "One"})
    await assert_database_count("posts", 1)
    await client.acting_as(user).post("/posts", json={"title": "Two"})
    await assert_database_count("posts", 2)


async def test_assert_model_exists_and_missing(user) -> None:
    from app.models.post import Post

    post = await Post.create(title="Direct create", body="", user_id=user.id)
    await assert_model_exists(post)

    await post.delete()
    await assert_model_missing(post)


async def test_assert_database_has_failure_message_is_helpful() -> None:
    with pytest.raises(AssertionError) as excinfo:
        await assert_database_has("posts", {"title": "Never created"})
    assert "posts" in str(excinfo.value)
    assert "Never created" in str(excinfo.value)


async def test_test_isolation_between_tests_sees_nothing_left_over() -> None:
    """Mirrors T-57's own "Testing" example: nothing from other tests in this file leaks in."""
    await assert_database_count("posts", 0)
