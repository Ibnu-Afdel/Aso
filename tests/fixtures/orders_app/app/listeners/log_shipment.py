"""A non-queued listener: records to a module-level list so the test can see it ran inline, in
the caller's own task and database scope (`tests/conftest.py` purges this module between tests,
so the list always starts empty)."""

from __future__ import annotations

from app.events.order_shipped import OrderShipped

calls: list[int] = []


class LogShipment:
    async def handle(self, event: OrderShipped) -> None:
        calls.append(event.order_id)
