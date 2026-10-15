"""Module-level `Event`/listener classes for `tests/events/` (T-46): importable by dotted path,
since `CallQueuedListener.handle()` reimports both the listener and the event class by their
`__module__.__qualname__` in the worker, regardless of queue driver."""

from __future__ import annotations

from fastogram.events import Event

calls: list[dict] = []


def reset() -> None:
    calls.clear()


class OrderShipped(Event):
    def __init__(self, order_id: int) -> None:
        self.order_id = order_id


class OtherEvent(Event):
    def __init__(self, value: str) -> None:
        self.value = value


class UnserializableEvent(Event):
    def __init__(self, thing: object) -> None:
        self.thing = thing


class LogShipment:
    """Plain, non-queued listener."""

    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "log", "order_id": event.order_id})


class RaisingListener:
    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "raising", "order_id": event.order_id})
        raise RuntimeError("boom")


class NeverCalledListener:
    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "never", "order_id": event.order_id})  # pragma: no cover


class StatefulListener:
    """A fresh instance per dispatch: `self.seen` must never carry over between events."""

    def __init__(self) -> None:
        self.seen = False

    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "stateful", "seen_before": self.seen})
        self.seen = True


class QueuedListener:
    queued = True
    queue = "emails"
    tries = 3
    backoff = [10, 60]
    timeout = 45

    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "queued", "order_id": event.order_id})

    async def failed(self, event: OrderShipped, exc: Exception) -> None:
        calls.append({"listener": "queued-failed", "order_id": event.order_id, "error": str(exc)})


class QueuedDefaultOptionsListener:
    """No explicit `queue`/`tries`/`backoff`/`timeout`/`after_commit`: checks the T-46 defaults,
    in particular `after_commit = True` (unlike a plain `Job`, which defaults to `False`)."""

    queued = True

    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "queued-default", "order_id": event.order_id})


class QueuedAfterCommitFalseListener:
    queued = True
    after_commit = False

    async def handle(self, event: OrderShipped) -> None:
        calls.append({"listener": "queued-no-after-commit", "order_id": event.order_id})


class QueuedFailingListener:
    queued = True
    tries = 1

    async def handle(self, event: OrderShipped) -> None:
        raise RuntimeError("queued boom")
