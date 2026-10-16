"""`Event.dispatch()`: inline, in order, caller's own task/context (T-46)."""

from __future__ import annotations

import _event_fixtures as _fixtures
import pytest

from aso.events import Event


async def test_dispatch_with_no_listeners_is_a_noop():
    assert await _fixtures.OrderShipped(order_id=1).dispatch() is None
    assert _fixtures.calls == []


async def test_dispatch_runs_non_queued_listeners_inline_in_order():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.listen(_fixtures.OrderShipped, _fixtures.NeverCalledListener)

    result = await _fixtures.OrderShipped(order_id=7).dispatch()

    assert result is None
    assert _fixtures.calls == [
        {"listener": "log", "order_id": 7},
        {"listener": "never", "order_id": 7},
    ]


async def test_a_new_listener_instance_is_built_per_dispatch():
    Event.listen(_fixtures.OrderShipped, _fixtures.StatefulListener)

    await _fixtures.OrderShipped(order_id=1).dispatch()
    await _fixtures.OrderShipped(order_id=2).dispatch()

    assert _fixtures.calls == [
        {"listener": "stateful", "seen_before": False},
        {"listener": "stateful", "seen_before": False},
    ]


async def test_listener_exception_propagates_and_stops_the_chain():
    Event.listen(_fixtures.OrderShipped, _fixtures.RaisingListener)
    Event.listen(_fixtures.OrderShipped, _fixtures.NeverCalledListener)

    with pytest.raises(RuntimeError, match="boom"):
        await _fixtures.OrderShipped(order_id=1).dispatch()

    assert _fixtures.calls == [{"listener": "raising", "order_id": 1}]


async def test_dispatch_only_matches_the_exact_event_type():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    await _fixtures.OtherEvent(value="x").dispatch()
    assert _fixtures.calls == []
