"""T-56: `TestResponse` assertion helpers (status, session, headers, cookies, JSON, text)."""

from __future__ import annotations

import pytest

from fastogram.testing.client import TestClient


async def test_status_helpers(client: TestClient) -> None:
    (await client.get("/posts")).assert_ok()
    (await client.get("/posts")).assert_successful()
    (await client.get("/nope")).assert_not_found()
    (await client.get("/posts/999")).assert_not_found()


async def test_assert_ok_raises_with_a_helpful_message_on_mismatch(client: TestClient) -> None:
    response = await client.get("/nope")
    with pytest.raises(AssertionError) as excinfo:
        response.assert_ok()
    message = str(excinfo.value)
    assert "200" in message
    assert "404" in message


async def test_assert_json_validation_errors_dict_form(client: TestClient) -> None:
    response = await client.post_json("/api/posts", {"title": "x"})
    response.assert_json_validation_errors({"title": "The title field must be at least 3 characters."})


async def test_assert_unprocessable_and_validation_errors(client: TestClient) -> None:
    response = await client.post_json("/api/posts", {"title": "x"})
    response.assert_unprocessable()
    response.assert_json_validation_errors(["title"])


async def test_assert_redirect_to_route(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/posts", json={"title": "Routed post"})
    response.assert_redirect_to_route("posts.index")


async def test_session_assertions(client: TestClient) -> None:
    response = await client.from_url("/posts/create").post("/posts", json={"title": "x"})
    response.assert_session_has_errors(["title"])
    response.assert_session_has_errors({"title": "The title field must be at least 3 characters."})
    response.assert_session_missing("success")


async def test_session_has_errors_partial_match(client: TestClient) -> None:
    response = await client.from_url("/posts/create").post("/posts", json={"title": "x"})
    response.assert_session_has_errors({"title": "at least 3 characters"}, partial=True)


async def test_assert_session_has_no_errors_on_success(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/posts", json={"title": "Totally fine title"})
    response.assert_session_has_no_errors()
    response.assert_session_has("success", "Post created.")


async def test_headers_and_cookies(client: TestClient) -> None:
    response = await client.get("/posts")
    response.assert_header("content-type")
    response.assert_cookie("testing-app-session")
    response.assert_cookie_missing("does-not-exist")


async def test_assert_see_escapes_by_default(client: TestClient, user) -> None:
    response = await client.acting_as(user).get("/posts")
    response.assert_see("posts/index", escape=False)


async def test_json_assertions(client: TestClient) -> None:
    response = await client.get("/api/posts")
    response.assert_ok()
    response.assert_json({"status": "ok"})
    response.assert_json_path("status", "ok")
    response.assert_json_count(0, "data")


async def test_exact_json(client: TestClient) -> None:
    response = await client.get("/api/posts")
    response.assert_exact_json({"data": [], "status": "ok"})
