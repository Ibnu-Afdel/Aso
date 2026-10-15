"""Events and listeners (T-46, D-027): `Event`, `Event.listen()`, queued listeners.

```python
from fastogram.events import Event

class OrderShipped(Event):
    def __init__(self, order_id: int) -> None:
        self.order_id = order_id

Event.listen(OrderShipped, SendShipmentNotification)   # in create_app()
await OrderShipped(order_id=order.id).dispatch()
```

A listener is a plain class with `async def handle(self, event)`; set `queued = True` (plus
`queue`/`tries`/`backoff`/`timeout`/`after_commit`) to run it as the built-in `CallQueuedListener`
job instead of inline.
"""

from __future__ import annotations

from fastogram.events.event import Event, reset_events
from fastogram.events.listener_job import CallQueuedListener

__all__ = ["CallQueuedListener", "Event", "reset_events"]
