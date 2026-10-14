"""End-to-end middleware-pipeline tests through the real ASGI stack (T-11): execution order,
priority reordering, parameters, short-circuiting, header mutation, `terminate()`, streaming
passthrough, exceptions rendered at depth (session still saved), `without_middleware()`, and
controller-declared `only=`/`except_=`."""

from __future__ import annotations

import httpx2 as httpx


async def test_middleware_runs_before_and_after_the_controller_then_terminates(client: httpx.AsyncClient, mw_state):
    """`/mw/order` nests `mw_a` outside `mw_b`: `before:a` and `before:b` must run in that order,
    and `mw_a`'s `terminate()` must run once the response has been sent."""
    r = await client.get("/mw/order")
    assert r.status_code == 200
    record = mw_state["record"]
    assert record[0] == "before:a"
    assert record[1] == "before:b"
    assert record[-1] == "terminate:a"
    assert set(record) == {"before:a", "before:b", "after:a", "after:b", "terminate:a"}


async def test_priority_reorders_execution_regardless_of_registration_order(client: httpx.AsyncClient, mw_state):
    """`/mw/priority` lists `.middleware("mw_b", "mw_a")`, but the app's `m.priority(["mw_a",
    "mw_b", "bindings"])` must still make `mw_a` run before `mw_b` at runtime."""
    r = await client.get("/mw/priority")
    assert r.status_code == 200
    record = mw_state["record"]
    assert record.index("before:a") < record.index("before:b")


async def test_short_circuit_middleware_prevents_the_inner_app_from_running(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/short")
    assert r.status_code == 200
    assert r.json() == {"short": True}
    assert mw_state["inner_ran"]["value"] is False


async def test_header_mutator_middleware_can_change_response_headers(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/header")
    assert r.status_code == 200
    assert r.headers["X-Mutated"] == "yes"


async def test_middleware_with_parameters(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/secure", headers={"X-Role": "editor"})
    assert r.status_code == 200
    r = await client.get("/mw/secure", headers={"X-Role": "viewer"})
    assert r.status_code == 403


async def test_custom_group_expands_its_members_in_order(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/admin-group")
    assert r.status_code == 200
    assert mw_state["record"] == ["before:c", "before:d", "after:d", "after:c"]


async def test_streaming_response_passes_through_untouched(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/stream")
    assert r.status_code == 200
    assert r.text == "line 0\nline 1\nline 2\n"


async def test_middleware_exception_is_rendered_at_that_depth_and_session_is_still_saved(client: httpx.AsyncClient, mw_state):
    """`Raiser` aborts before calling `next()`. The response must still carry the session/XSRF
    cookies that the *outer* layers (StartSession, PreventRequestForgery) set on the way out."""
    r = await client.get("/mw/raise")
    assert r.status_code == 400
    set_cookie = r.headers.get("set-cookie", "")
    assert "XSRF-TOKEN" in set_cookie


async def test_without_middleware_removes_a_route_middleware(client: httpx.AsyncClient, mw_state):
    r = await client.get("/gated")
    assert mw_state["record"] == ["before:a", "after:a", "terminate:a"]
    mw_state["record"].clear()
    r = await client.get("/gated-no-mw")
    assert r.status_code == 200
    assert mw_state["record"] == []


async def test_controller_declared_middleware_only_limits_it_to_that_action(client: httpx.AsyncClient, mw_state):
    r = await client.get("/gated")
    assert r.status_code == 200
    assert mw_state["record"] == ["before:a", "after:a", "terminate:a"]
    mw_state["record"].clear()

    r = await client.get("/open")
    assert r.status_code == 200
    assert mw_state["record"] == []


async def test_body_is_readable_by_middleware_and_then_still_by_the_controller(client: httpx.AsyncClient, mw_state):
    await client.get("/misc/ping")
    xsrf = {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN", "")}
    r = await client.post("/misc/body", json={"x": "hello"}, headers=xsrf)
    assert r.status_code == 200
    assert r.json() == {"x": "hello"}
    assert mw_state["peek"] == ["peek:hello"]
