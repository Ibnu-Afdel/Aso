"""`CallQueuedListener`: the built-in job that runs a queued listener in the worker (T-46).

The event is rebuilt **without calling `__init__`** (`cls.__new__(cls)` + `__dict__.update`),
exactly like a job's own constructor arguments (T-42), since a queued listener's event must hold
ids only.
"""

from __future__ import annotations

import inspect
from typing import Any

from fastogram.queue.job import Job


class CallQueuedListener(Job):
    def __init__(self, *, listener: str, event_cls: str, event_args: dict[str, Any]) -> None:
        self.listener = listener
        self.event_cls = event_cls
        self.event_args = event_args

    async def handle(self) -> None:
        listener = _import(self.listener)()
        event = _rebuild_event(self.event_cls, self.event_args)
        await listener.handle(event)

    async def failed(self, exc: Exception) -> None:
        listener = _import(self.listener)()
        failed_fn = getattr(listener, "failed", None)
        if not callable(failed_fn):
            return
        event = _rebuild_event(self.event_cls, self.event_args)
        result = failed_fn(event, exc)
        if inspect.isawaitable(result):
            await result


def _rebuild_event(event_cls_path: str, event_args: dict[str, Any]) -> Any:
    event_cls = _import(event_cls_path)
    event = event_cls.__new__(event_cls)
    event.__dict__.update(event_args)
    return event


def _import(dotted: str) -> Any:
    import importlib

    module_name, _, name = dotted.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, name)
