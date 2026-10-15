"""`Event.listen()` / `listeners_for()` / `assert_listening()` (T-46, D-027)."""

from __future__ import annotations

import _event_fixtures as _fixtures

from fastogram.events import Event


def test_listen_registers_in_order():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)
    assert Event.listeners_for(_fixtures.OrderShipped) == [_fixtures.LogShipment, _fixtures.QueuedListener]


def test_duplicate_listen_pair_is_ignored():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    assert Event.listeners_for(_fixtures.OrderShipped) == [_fixtures.LogShipment]


def test_same_listener_on_two_events_is_not_a_duplicate():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.listen(_fixtures.OtherEvent, _fixtures.LogShipment)
    assert Event.listeners_for(_fixtures.OrderShipped) == [_fixtures.LogShipment]
    assert Event.listeners_for(_fixtures.OtherEvent) == [_fixtures.LogShipment]


def test_listeners_for_unregistered_event_is_empty():
    assert Event.listeners_for(_fixtures.OrderShipped) == []


def test_assert_listening_passes_when_registered():
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    Event.assert_listening(_fixtures.OrderShipped, _fixtures.LogShipment)


def test_assert_listening_fails_when_not_registered():
    import pytest

    with pytest.raises(AssertionError):
        Event.assert_listening(_fixtures.OrderShipped, _fixtures.LogShipment)


def test_listening_is_exact_class_only():
    """"A listener listens to the exact class it is registered for" (T-46): a subclass of the
    registered event is not matched."""

    class MoreSpecificShipped(_fixtures.OrderShipped):
        pass

    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)
    assert Event.listeners_for(MoreSpecificShipped) == []
