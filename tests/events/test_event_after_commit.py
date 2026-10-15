"""`after_commit` on queued listeners, defaulting to `True` (T-46): dispatched inside
`DB.transaction()`, the `CallQueuedListener` job waits for the commit."""

from __future__ import annotations

import _event_fixtures as _fixtures

from fastogram.database.db import DB
from fastogram.events import Event


async def test_queued_listener_waits_for_the_enclosing_transaction_to_commit(db):
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)

    async with DB.transaction():
        await _fixtures.OrderShipped(order_id=1).dispatch()
        assert _fixtures.calls == [], "after_commit defaults to True on a queued listener"

    assert _fixtures.calls == [{"listener": "queued", "order_id": 1}]


async def test_queued_listener_never_runs_if_the_transaction_rolls_back(db):
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedListener)

    class Boom(Exception):
        pass

    try:
        async with DB.transaction():
            await _fixtures.OrderShipped(order_id=1).dispatch()
            raise Boom
    except Boom:
        pass

    assert _fixtures.calls == []


async def test_non_queued_listener_runs_immediately_even_inside_a_transaction(db):
    """Only queued listeners defer; a plain listener runs right away, like a non-`after_commit`
    job (T-46)."""
    Event.listen(_fixtures.OrderShipped, _fixtures.LogShipment)

    async with DB.transaction():
        await _fixtures.OrderShipped(order_id=1).dispatch()
        assert _fixtures.calls == [{"listener": "log", "order_id": 1}]


async def test_queued_listener_with_after_commit_false_runs_immediately(db):
    Event.listen(_fixtures.OrderShipped, _fixtures.QueuedAfterCommitFalseListener)

    async with DB.transaction():
        await _fixtures.OrderShipped(order_id=1).dispatch()
        assert _fixtures.calls == [{"listener": "queued-no-after-commit", "order_id": 1}]
