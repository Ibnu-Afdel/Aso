"""`dispatch_after_response()` (T-42): stores the job on the request context's `extras`; a
foundation-level hook (not ours, see the build report) drains it after the response is sent."""

from __future__ import annotations

import _jobs
import pytest

from aso import context
from aso.queue.manager import drain_after_response


def _enter_context():
    ctx = context.RequestContext(scope={})
    return context.enter(ctx), ctx


async def test_dispatch_after_response_needs_a_request_context():
    with pytest.raises(RuntimeError):
        _jobs.EchoJob(value="x").dispatch_after_response()


async def test_dispatch_after_response_stores_then_drains_runs_the_job():
    token, ctx = _enter_context()
    try:
        _jobs.EchoJob(value="x").dispatch_after_response()
        assert _jobs.calls == []
        assert len(ctx.extras["queue.after_response"]) == 1
        await drain_after_response()
        assert _jobs.calls == [{"job": "echo", "value": "x", "session_id": None}]
        assert "queue.after_response" not in ctx.extras
    finally:
        context.leave(token)


async def test_drain_after_response_is_a_noop_outside_a_request():
    await drain_after_response()  # must not raise
