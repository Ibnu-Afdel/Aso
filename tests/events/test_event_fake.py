"""`Event.fake()` + class-level assertions (T-46)."""

from __future__ import annotations

import _event_fixtures as _fixtures
import pytest

from fastogram.events import Event


async def test_fake_records_instead_of_running_listeners():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.fake()

    await _fixtures.OrderShipped(order_id=1).dispatch()

    assert _fixtures.calls == []
    Event.assert_dispatched(_fixtures.OrderShipped)
    Event.assert_dispatched(_fixtures.OrderShipped, lambda event: event.order_id == 1)
    Event.assert_dispatched_times(_fixtures.OrderShipped, 1)


async def test_fake_leaves_the_listener_registry_alone():
    """`assert_listening()` still works under `Event.fake()` (T-46)."""
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.fake()
    Event.assert_listening(_fixtures.OrderShipped, _fixtures.LogShipment)


async def test_assert_not_dispatched():
    Event.fake()
    Event.assert_not_dispatched(_fixtures.OrderShipped)
    await _fixtures.OrderShipped(order_id=1).dispatch()
    with pytest.raises(AssertionError):
        Event.assert_not_dispatched(_fixtures.OrderShipped)


async def test_assert_nothing_dispatched():
    Event.fake()
    Event.assert_nothing_dispatched()
    await _fixtures.OrderShipped(order_id=1).dispatch()
    with pytest.raises(AssertionError):
        Event.assert_nothing_dispatched()


async def test_assert_dispatched_fails_when_not_dispatched():
    Event.fake()
    with pytest.raises(AssertionError):
        Event.assert_dispatched(_fixtures.OrderShipped)


async def test_assert_dispatched_times_fails_on_mismatch():
    Event.fake()
    await _fixtures.OrderShipped(order_id=1).dispatch()
    with pytest.raises(AssertionError):
        Event.assert_dispatched_times(_fixtures.OrderShipped, 2)


async def test_fake_does_not_cross_match_other_event_types():
    Event.fake()
    await _fixtures.OtherEvent(value="x").dispatch()
    with pytest.raises(AssertionError):
        Event.assert_dispatched(_fixtures.OrderShipped)


async def test_calling_a_listener_directly_bypasses_the_dispatcher():
    """"To test a listener itself, call it directly" (T-46) -- `Mail.fake()`-style unit testing
    of `handle()` without going through `dispatch()`/`Event.fake()` at all."""
    await _fixtures.LogShipment().handle(_fixtures.OrderShipped(order_id=11))
    assert _fixtures.calls == [{"listener": "log", "order_id": 11}]
