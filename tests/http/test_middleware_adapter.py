"""End-to-end tests for the `Middleware`/`Next` adapter (T-11): `HandleAdapter` turns the
`handle(request, next)` API into pure ASGI. Most of the mechanics (order, priority, params,
`without_middleware`, controller `only=`/`except_=`) are covered in
`tests/routing/test_feature_middleware.py` and `tests/routing/test_pipeline_unit.py`; this file
focuses on the adapter's own properties: short-circuiting, header mutation, streaming
passthrough, and exceptions rendered at that depth while outer layers still run."""

from __future__ import annotations

import httpx2 as httpx


async def test_short_circuit_middleware_never_runs_the_inner_app(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/short")
    assert r.json() == {"short": True}
    assert mw_state["inner_ran"]["value"] is False


async def test_header_mutation_after_next_resolves(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/header")
    assert r.status_code == 200
    assert r.headers["X-Mutated"] == "yes"
    # the inner endpoint still ran and its body is untouched.
    assert r.json() == {"ok": True}


async def test_streaming_response_is_not_buffered_by_an_untouching_middleware(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/stream")
    assert r.status_code == 200
    assert r.text == "line 0\nline 1\nline 2\n"


async def test_exception_in_middleware_is_rendered_at_that_depth(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/raise")
    assert r.status_code == 400


async def test_outer_layers_still_run_when_a_route_middleware_raises(client: httpx.AsyncClient, mw_state):
    """StartSession/PreventRequestForgery wrap the whole route pipeline (T-06); a `raiser` deep
    inside must not stop them from running on the way out -- the error response still carries
    the session cookies."""
    r = await client.get("/mw/raise")
    assert r.status_code == 400
    set_cookie = r.headers.get("set-cookie", "")
    assert "routing-session" in set_cookie
    assert "XSRF-TOKEN" in set_cookie


async def test_terminate_runs_after_the_response_is_sent(client: httpx.AsyncClient, mw_state):
    r = await client.get("/mw/order")
    assert r.status_code == 200
    assert mw_state["record"][-1] == "terminate:a"
