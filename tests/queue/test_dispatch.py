"""`Job.dispatch()` / `dispatch_sync()` on the `sync` driver (T-42): runs inline, reuses the
caller's database scope, validates args at dispatch time."""

from __future__ import annotations

import _jobs
import pytest

from fastogram.queue import JobNotSerializable
from fastogram.queue.job import Job


async def test_dispatch_runs_inline_on_sync_driver():
    await _jobs.EchoJob(value="hi").dispatch()
    assert _jobs.calls == [{"job": "echo", "value": "hi", "session_id": None}]


async def test_dispatch_sync_runs_inline_too():
    await _jobs.EchoJob(value="hi").dispatch_sync()
    assert _jobs.calls == [{"job": "echo", "value": "hi", "session_id": None}]


async def test_dispatch_reuses_callers_db_scope(db):
    from fastogram.database.scope import current_scope

    outer_session_id = id(current_scope().session())
    await _jobs.EchoJob(value="x").dispatch()
    assert _jobs.calls[0]["session_id"] == outer_session_id


async def test_not_serializable_args_raise_before_handle_runs():
    with pytest.raises(JobNotSerializable):
        await _jobs.BadJob(thing=object()).dispatch()
    assert _jobs.calls == []


async def test_not_serializable_args_raise_on_dispatch_sync_too():
    with pytest.raises(JobNotSerializable):
        await _jobs.BadJob(thing=object()).dispatch_sync()


async def test_sync_dispatch_failure_calls_failed_then_reraises(db):
    with pytest.raises(RuntimeError, match="boom:x"):
        await _jobs.AlwaysFailsJob(label="x").dispatch()
    kinds = [c["job"] for c in _jobs.calls]
    assert kinds == ["fail", "failed"]


async def test_sync_dispatch_failure_is_recorded_in_failed_jobs(db):
    from fastogram.queue.failed import list_failed

    with pytest.raises(RuntimeError):
        await _jobs.AlwaysFailsJob(label="y").dispatch()
    rows = await list_failed()
    assert len(rows) == 1
    assert "boom:y" in rows[0]["exception"]
    assert rows[0]["connection"] == "sync"


async def test_job_base_handle_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await Job().handle()
