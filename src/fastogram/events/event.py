"""`Event`: the dispatcher, registry and `Event.fake()` assertions (T-46, D-027).

```python
class OrderShipped(Event):
    def __init__(self, order_id: int) -> None:
        self.order_id = order_id

Event.listen(OrderShipped, SendShipmentNotification)
await OrderShipped(order_id=order.id).dispatch()
```
"""

from __future__ import annotations

from typing import Any, ClassVar


class Event:
    """Subclass and set attributes in `__init__`. Dispatch with `await event.dispatch()`."""

    _listeners: ClassVar[dict[type[Event], list[type]]] = {}
    _fake: ClassVar[bool] = False
    _dispatched: ClassVar[list[Event]] = []

    # ------------------------------------------------------------ registry

    @classmethod
    def listen(cls, event_cls: type[Event], listener_cls: type) -> None:
        """Register `listener_cls` for `event_cls`. A duplicate pair is ignored (T-46)."""
        listeners = Event._listeners.setdefault(event_cls, [])
        if listener_cls not in listeners:
            listeners.append(listener_cls)

    @classmethod
    def listeners_for(cls, event_cls: type[Event]) -> list[type]:
        return list(Event._listeners.get(event_cls, []))

    # ------------------------------------------------------------ fake + assertions

    @classmethod
    def fake(cls) -> None:
        """Stop listeners from running; record dispatched events instead. The listener registry
        is untouched, so `assert_listening()` still works."""
        Event._fake = True
        Event._dispatched = []

    @classmethod
    def reset(cls) -> None:
        """Test isolation: drop the fake and anything it recorded (not the listener registry --
        see `fastogram.events.reset_events()` for that)."""
        Event._fake = False
        Event._dispatched = []

    @classmethod
    def assert_dispatched(cls, event_cls: type[Event], check: Any = None) -> None:
        matches = [e for e in Event._dispatched if type(e) is event_cls and (check is None or check(e))]
        assert matches, f"The event [{event_cls.__name__}] was not dispatched."

    @classmethod
    def assert_dispatched_times(cls, event_cls: type[Event], times: int) -> None:
        matches = [e for e in Event._dispatched if type(e) is event_cls]
        assert len(matches) == times, (
            f"The event [{event_cls.__name__}] was dispatched {len(matches)} time(s), expected {times}."
        )

    @classmethod
    def assert_not_dispatched(cls, event_cls: type[Event], check: Any = None) -> None:
        matches = [e for e in Event._dispatched if type(e) is event_cls and (check is None or check(e))]
        assert not matches, f"The event [{event_cls.__name__}] was dispatched."

    @classmethod
    def assert_nothing_dispatched(cls) -> None:
        assert not Event._dispatched, f"{len(Event._dispatched)} event(s) were dispatched."

    @classmethod
    def assert_listening(cls, event_cls: type[Event], listener_cls: type) -> None:
        assert listener_cls in Event._listeners.get(event_cls, []), (
            f"[{listener_cls.__name__}] is not listening to [{event_cls.__name__}]."
        )

    # ------------------------------------------------------------ dispatch

    async def dispatch(self) -> None:
        """Run every registered listener in order (non-queued ones inline; queued ones as a
        `CallQueuedListener` job), or just record this event when `Event.fake()` is on."""
        if Event._fake:
            Event._dispatched.append(self)
            return
        listeners = Event.listeners_for(type(self))
        if not listeners:
            return
        if any(getattr(listener_cls, "queued", False) for listener_cls in listeners):
            from fastogram.queue.serialization import validate_serializable

            validate_serializable(vars(self))  # raise JobNotSerializable before anything runs
        for listener_cls in listeners:
            if getattr(listener_cls, "queued", False):
                await _dispatch_queued(listener_cls, self)
            else:
                await listener_cls().handle(self)


async def _dispatch_queued(listener_cls: type, event: Event) -> None:
    from fastogram.events.listener_job import CallQueuedListener

    job = CallQueuedListener(
        listener=f"{listener_cls.__module__}.{listener_cls.__qualname__}",
        event_cls=f"{type(event).__module__}.{type(event).__qualname__}",
        event_args=dict(vars(event)),
    )
    job.queue = getattr(listener_cls, "queue", "default")
    job.tries = getattr(listener_cls, "tries", 1)
    job.backoff = getattr(listener_cls, "backoff", 0)
    job.timeout = getattr(listener_cls, "timeout", 60)
    job.after_commit = getattr(listener_cls, "after_commit", True)  # T-46: True by default when queued
    await job.dispatch()


def reset_events() -> None:
    """Test isolation: `Event.reset()` plus clear the listener registry.

    The registry holds class objects as keys/values; between fixture apps those classes are
    reimported under the same dotted names (`tests/conftest.py` purges `app.*`/`routes.*` etc
    from `sys.modules` before every test), so stale entries would otherwise accumulate for the
    life of the test process. See the build report for the exact `tests/conftest.py` addition.
    """
    Event.reset()
    Event._listeners = {}
