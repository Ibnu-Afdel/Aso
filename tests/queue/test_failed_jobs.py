"""The `failed_jobs` store (T-42): what `queue:failed/retry/forget/flush` will call."""

from __future__ import annotations

import _jobs

from aso.queue.failed import flush_failed, forget_failed, list_failed, retry_failed
from aso.queue.manager import run_job


async def test_record_and_list(db):
    payload = _jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "a"}, tries=1)
    await run_job(payload)
    rows = await list_failed()
    assert len(rows) == 1
    assert rows[0]["queue"] == "default"
    assert rows[0]["connection"] == "sync"


async def test_forget_removes_one_row(db):
    await run_job(_jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "a"}, tries=1))
    rows = await list_failed()
    assert await forget_failed(rows[0]["id"]) is True
    assert await list_failed() == []
    assert await forget_failed(rows[0]["id"]) is False


async def test_flush_removes_every_row(db):
    await run_job(_jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "a"}, tries=1))
    await run_job(_jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "b"}, tries=1))
    assert len(await list_failed()) == 2
    removed = await flush_failed()
    assert removed == 2
    assert await list_failed() == []


async def test_retry_one_by_id_redispatches_and_forgets_the_row(db):
    await run_job(_jobs.make_payload(_jobs.FlakyJob, {"key": "r", "fail_times": 5}, tries=1))
    rows = await list_failed()
    assert len(rows) == 1
    retried = await retry_failed(rows[0]["id"])
    assert retried == 1
    # retried on the `sync` connection: runs immediately again (attempt 1), fails again, re-queued
    assert _jobs.attempts["r"] == 2
    assert len(await list_failed()) == 1  # the new failure, not the old row


async def test_retry_all(db):
    await run_job(_jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "a"}, tries=1))
    await run_job(_jobs.make_payload(_jobs.AlwaysFailsJob, {"label": "b"}, tries=1))
    retried = await retry_failed("all")
    assert retried == 2
