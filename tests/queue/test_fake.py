"""`Queue.fake()` + class-level assertions (T-42)."""

from __future__ import annotations

import _jobs
import pytest

from aso.queue import Queue


async def test_fake_records_instead_of_running():
    Queue.fake()
    await _jobs.EchoJob(value="a").dispatch()
    assert _jobs.calls == []
    Queue.assert_dispatched(_jobs.EchoJob)
    Queue.assert_dispatched(_jobs.EchoJob, lambda job: job.value == "a")
    Queue.assert_dispatched_times(_jobs.EchoJob, 1)


async def test_fake_records_dispatch_sync_too():
    Queue.fake()
    await _jobs.EchoJob(value="a").dispatch_sync()
    Queue.assert_dispatched_times(_jobs.EchoJob, 1)


async def test_assert_not_dispatched():
    Queue.fake()
    Queue.assert_not_dispatched(_jobs.EchoJob)
    await _jobs.EchoJob(value="a").dispatch()
    with pytest.raises(AssertionError):
        Queue.assert_not_dispatched(_jobs.EchoJob)


async def test_assert_nothing_dispatched():
    Queue.fake()
    Queue.assert_nothing_dispatched()
    await _jobs.EchoJob(value="a").dispatch()
    with pytest.raises(AssertionError):
        Queue.assert_nothing_dispatched()


async def test_assert_dispatched_fails_when_not_dispatched():
    Queue.fake()
    with pytest.raises(AssertionError):
        Queue.assert_dispatched(_jobs.EchoJob)


async def test_assert_dispatched_times_fails_on_mismatch():
    Queue.fake()
    await _jobs.EchoJob(value="a").dispatch()
    with pytest.raises(AssertionError):
        Queue.assert_dispatched_times(_jobs.EchoJob, 2)


async def test_fake_still_validates_serializability():
    from aso.queue import JobNotSerializable

    Queue.fake()
    with pytest.raises(JobNotSerializable):
        await _jobs.BadJob(thing=object()).dispatch()
