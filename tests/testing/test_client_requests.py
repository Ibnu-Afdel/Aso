"""T-56: `TestClient` methods and fluent modifiers, against `tests/fixtures/testing_app`."""

from __future__ import annotations

from aso.testing.client import TestClient


async def test_get_and_put_patch_delete_through_the_real_stack(client: TestClient) -> None:
    response = await client.get("/posts")
    response.assert_ok()

    response = await client.put("/posts/create", json={})
    # `/posts/create` is a GET-only route -> no PUT handler matches it (still a real HTTP
    # response, not a connection error) -- exercises `put`/`patch`/`delete` all going through
    # `_request` the same way `get`/`post` do.
    assert response.status_code in (404, 405)
    response = await client.patch("/posts/create", json={})
    assert response.status_code in (404, 405)
    response = await client.delete("/posts/create")
    assert response.status_code in (404, 405)


async def test_post_json_sends_json_accept_header(client: TestClient) -> None:
    response = await client.post_json("/api/posts", {"title": "ab"})
    response.assert_status(422)
    response.assert_json_validation_errors(["title"])


async def test_acting_as_logs_in_through_the_session_store(client: TestClient, user) -> None:
    await client.acting_as(user).get("/posts")
    await client.assert_authenticated_as(user)


async def test_acting_as_persists_across_later_requests_from_the_same_client(client: TestClient, user) -> None:
    logged_in = client.acting_as(user)
    await logged_in.get("/posts")
    await logged_in.get("/posts")
    await logged_in.assert_authenticated_as(user)


async def test_guest_client_is_not_authenticated(client: TestClient) -> None:
    await client.get("/posts")
    await client.assert_guest()


async def test_with_session_merges_into_the_session_store(client: TestClient) -> None:
    response = await client.with_session({"cart": {"items": [1, 2]}}).get("/posts")
    response.assert_session_has("cart.items", [1, 2])


async def test_from_url_sets_referer_for_back_redirects(client: TestClient) -> None:
    response = await client.from_url("/posts/create").post("/posts", json={"title": "x"})
    response.assert_redirect("/posts/create")


async def test_with_headers_applies_to_the_request(client: TestClient) -> None:
    response = await client.with_headers({"X-Locale": "fr"}).get("/posts")
    response.assert_ok()


async def test_with_cookie_sends_an_arbitrary_cookie(client: TestClient) -> None:
    response = await client.with_cookie("appearance", "dark").get("/posts")
    response.assert_ok()
    assert response._response.request.headers.get("cookie", "").find("appearance=dark") != -1


async def test_inertia_modifier_sends_inertia_headers(client: TestClient) -> None:
    response = await client.inertia().get("/posts")
    response.assert_header("X-Inertia", "true")
    response.assert_inertia(lambda page: page.component("posts/index").etc())


async def test_inertia_with_stale_version_gets_409(client: TestClient) -> None:
    response = await client.inertia(version="stale-version").get("/posts")
    response.assert_status(409)


async def test_with_csrf_turns_checking_back_on(client: TestClient) -> None:
    response = await (
        client.inertia().from_url("/posts/create").with_csrf().post("/posts", json={"title": "Hello world"})
    )
    # No X-XSRF-TOKEN supplied -> CSRF now enforced -> redirected back with a flash error
    # (T-12's Inertia-visit branch; `aso.testing.plugin`'s `db` fixture leaves CSRF off
    # by default, which is why every *other* test in this file can post without a token).
    response.assert_redirect("/posts/create")
    response.assert_session_has("error")


async def test_without_csrf_posts_succeed_in_testing_by_default(client: TestClient, user) -> None:
    response = await client.acting_as(user).post("/posts", json={"title": "No csrf needed"})
    response.assert_redirect()


async def test_with_exception_handling_false_lets_exceptions_raise(client: TestClient) -> None:
    import pytest

    calling_client = client.with_exception_handling(False)
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        # No form body at all -> FastAPI/pydantic validation blows up loudly instead of being
        # rendered into a 422 by the handler.
        await calling_client.post("/posts", data=b"not-json", headers={"Content-Type": "application/json"})


async def test_follow_redirects_follows_to_the_final_page(client: TestClient, user) -> None:
    response = await (
        client.acting_as(user).follow_redirects().inertia().post("/posts", json={"title": "Followed post"})
    )
    response.assert_ok()
    response.assert_inertia(lambda page: page.component("posts/index").etc())


async def test_without_middleware_skips_the_alias_only_in_testing(client: TestClient) -> None:
    (await client.get("/guarded")).assert_redirect()
    (await client.without_middleware("auth").get("/guarded")).assert_ok()
    (await client.without_middleware().get("/guarded")).assert_ok()

    from aso.config import set_config

    set_config("app.environment", "production")  # the flag must never work outside tests
    try:
        (await client.without_middleware("auth").get("/guarded")).assert_redirect()
    finally:
        set_config("app.environment", "testing")
