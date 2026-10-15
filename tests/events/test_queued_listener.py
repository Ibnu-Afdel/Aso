"""Queued listeners: dispatched as `CallQueuedListener` jobs, with the `Job` options read off
the listener class and `after_commit` defaulting to `True` (T-46, D-027)."""

from __future__ import annotations

import _event_fixtures as _fixtures
import pytest

from fastogram.events import CallQueuedListener, Event
from fastogram.queue import JobNotSerializable, Queue


async def test_queued_listener_dispatches_a_call_queued_listener_job():
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)
    Queue.fake()

    await _fixtures.OrderShipped(order_id=9).dispatch()

    Queue.assert_dispatched_times(CallQueuedListener, 1)
    Queue.assert_dispatched(
        CallQueuedListener,
        lambda job: job.listener.endswith("QueuedListener")
        and job.event_cls.endswith("OrderShipped")
        and job.event_args == {"order_id": 9},
    )


async def test_queued_listener_options_come_from_the_listener_class():
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)
    Queue.fake()

    await _fixtures.OrderShipped(order_id=1).dispatch()

    job = Queue._dispatched[0][1]
    assert job.queue == "emails"
    assert job.tries == 3
    assert job.backoff == [10, 60]
    assert job.timeout == 45


async def test_queued_listener_after_commit_defaults_to_true():
    """Unlike a plain `Job` (default `False`), a queued listener with no explicit `after_commit`
    defaults to `True` (T-46)."""
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedDefaultOptionsListener)
    Queue.fake()

    await _fixtures.OrderShipped(order_id=1).dispatch()

    job = Queue._dispatched[0][1]
    assert job.after_commit is True


async def test_queued_listener_after_commit_can_be_overridden():
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedAfterCommitFalseListener)
    Queue.fake()

    await _fixtures.OrderShipped(order_id=1).dispatch()

    job = Queue._dispatched[0][1]
    assert job.after_commit is False


async def test_non_serializable_event_raises_before_any_listener_runs():
    """"If an attribute of the event is not JSON-serialisable ... `dispatch()` raises
    `JobNotSerializable` before any listener runs" (T-46) -- including non-queued ones ahead of
    the queued listener in registration order."""
    Event.listen(_fixtures.UnserializableEvent, _fixtures.NeverCalledListener)
    Event.listen(_fixtures.UnserializableEvent, _fixtures.QueuedListener)

    with pytest.raises(JobNotSerializable):
        await _fixtures.UnserializableEvent(thing=object()).dispatch()

    assert _fixtures.calls == []


async def test_serializable_event_with_only_non_queued_listeners_is_not_validated():
    """A plain (non-model) attribute is fine either way, but this also documents that
    serialisability is only enforced when a queued listener is present."""
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    await _fixtures.OrderShipped(order_id=1).dispatch()
    assert _fixtures.calls == [{"listener": "log", "order_id": 1}]


async def test_call_queued_listener_rebuilds_the_event_without_init_and_runs_the_listener():
    """In the worker: `CallQueuedListener.handle()` imports both classes by dotted path, rebuilds
    the event with `__new__` (never calling `__init__` again), and awaits
    `Listener().handle(event)` (T-46)."""
    job = CallQueuedListener(
        listener=f"{_fixtures.QueuedListener.__module__}.{_fixtures.QueuedListener.__qualname__}",
        event_cls=f"{_fixtures.OrderShipped.__module__}.{_fixtures.OrderShipped.__qualname__}",
        event_args={"order_id": 42},
    )

    await job.handle()

    assert _fixtures.calls == [{"listener": "queued", "order_id": 42}]


async def test_call_queued_listener_failed_calls_the_listeners_failed_hook():
    job = CallQueuedListener(
        listener=f"{_fixtures.QueuedListener.__module__}.{_fixtures.QueuedListener.__qualname__}",
        event_cls=f"{_fixtures.OrderShipped.__module__}.{_fixtures.OrderShipped.__qualname__}",
        event_args={"order_id": 5},
    )

    await job.failed(RuntimeError("boom"))

    assert _fixtures.calls == [{"listener": "queued-failed", "order_id": 5, "error": "boom"}]


async def test_call_queued_listener_failed_is_a_noop_without_a_failed_hook():
    """`QueuedDefaultOptionsListener` has no `failed()`; `CallQueuedListener.failed()` must not
    raise `AttributeError` just because the listener did not define one."""
    job = CallQueuedListener(
        listener=f"{_fixtures.QueuedDefaultOptionsListener.__module__}."
        f"{_fixtures.QueuedDefaultOptionsListener.__qualname__}",
        event_cls=f"{_fixtures.OrderShipped.__module__}.{_fixtures.OrderShipped.__qualname__}",
        event_args={"order_id": 5},
    )

    await job.failed(RuntimeError("boom"))  # must not raise


async def test_queued_listener_runs_end_to_end_on_the_sync_queue():
    """On the `sync` driver the listener runs inline, like any sync job (T-46)."""
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)

    await _fixtures.OrderShipped(order_id=3).dispatch()

    assert _fixtures.calls == [{"listener": "queued", "order_id": 3}]
