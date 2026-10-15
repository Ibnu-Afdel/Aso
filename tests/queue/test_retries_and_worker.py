"""`run_job()` (T-42 "Running a job"): retries with backoff, `release()`, final failure.

Builds payloads by hand (see `_jobs.make_payload`) with `connection="sync"`, so a redispatch on
failure/release loops straight back into `run_job()` in-process instead of needing a real broker
-- the retry *logic* is identical on every connection; only the transport differs (T-42).
"""

from __future__ import annotations

import _jobs
import pytest

from fastogram.queue.manager import _backoff_for, run_job


async def test_backoff_uses_the_last_value_past_the_end_of_the_list():
    assert _backoff_for([10, 60], 1) == 10
    assert _backoff_for([10, 60], 2) == 60
    assert _backoff_for([10, 60], 3) == 60
    assert _backoff_for(5, 1) == 5
    assert _backoff_for(5, 10) == 5
    assert _backoff_for([], 1) == 0


async def test_flaky_job_succeeds_after_enough_retries(db):
    payload = _jobs.make_payload(_jobs.FlakyJob, {"key": "a", "fail_times": 2}, tries=3, backoff=0)
    await run_job(payload)
    assert _jobs.attempts["a"] == 3
    from fastogram.queue.failed import list_failed

    assert await list_failed() == []


async def test_job_exhausting_tries_is_recorded_failed(db):
    payload = _jobs.make_payload(_jobs.FlakyJob, {"key": "b", "fail_times": 5}, tries=2, backoff=0)
    await run_job(payload)
    assert _jobs.attempts["b"] == 2
    from fastogram.queue.failed import list_failed

    rows = await list_failed()
    assert len(rows) == 1
    assert "flaky failure" in rows[0]["exception"]


async def test_tries_one_never_retries(db):
    payload = _jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "z"}, tries=1)
    await run_job(payload)
    kinds = [c["job"] for c in _jobs.calls]
    assert kinds == ["fail", "failed"]


async def test_release_puts_the_job_back_and_counts_as_an_attempt(db):
    payload = _jobs.make_payload(_jobs.ReleasingJob, {"key": "r"}, tries=3)
    await run_job(payload)
    assert _jobs.attempts["r"] == 2  # released once, then succeeded


async def test_release_past_tries_is_dropped_without_failing(db):
    payload = _jobs.make_payload(_jobs.ReleasingJob, {"key": "r2"}, tries=1)
    await run_job(payload)
    assert _jobs.attempts["r2"] == 1
    from fastogram.queue.failed import list_failed

    assert await list_failed() == []  # dropped silently: release() is not a failure


async def test_run_job_opens_a_fresh_scope_not_the_callers(db):
    from fastogram.database.scope import current_scope

    outer_session_id = id(current_scope().session())
    payload = _jobs.make_payload(_jobs.EchoJob, {"value": "worker"}, connection="redis")
    await run_job(payload)
    assert _jobs.calls[0]["session_id"] != outer_session_id


@pytest.mark.parametrize("tries", [1, 2])
async def test_unserializable_rebuild_args_never_happen_because_dispatch_validated(tries):
    # Sanity: run_job trusts the payload was already validated at dispatch time; it does not
    # re-validate. This test just documents that assumption holds for a normal payload.
    payload = _jobs.make_payload(_jobs.EchoJob, {"value": "ok"}, tries=tries)
    await run_job(payload)
    assert _jobs.calls[-1]["value"] == "ok"
