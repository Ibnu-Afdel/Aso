"""`Job`: the base class for background work (T-42).

```python
class SendWelcomeEmail(Job):
    tries = 3
    backoff = [10, 60]

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    async def handle(self) -> None: ...
```

Constructor arguments become the instance's `__dict__` and must be JSON-serialisable (pass ids,
not models): `dispatch()` validates them and raises `JobNotSerializable` immediately, never later
in the worker.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar

from aso.queue.serialization import validate_serializable


class Job:
    """Subclass this, set `__init__` to store JSON-safe constructor arguments, and implement
    `async def handle(self)`."""

    tries: ClassVar[int] = 1
    """Total attempts, including the first (Laravel default: no retry)."""

    backoff: ClassVar[int | list[int]] = 0
    """Seconds to wait before each retry. An int repeats; a list's last value repeats past its end."""

    timeout: ClassVar[int] = 60
    """Seconds before one attempt is cancelled."""

    queue: ClassVar[str] = "default"
    """The named queue this job is placed on, unless overridden by `dispatch(queue=...)`."""

    after_commit: ClassVar[bool] = False
    """Wait for the enclosing `DB.transaction()` to commit before sending (D-011). `False` by
    default on `Job`; the built-in `CallQueuedListener` (T-46) and `SendQueuedMail` (T-41) set it
    `True`, matching their pages."""

    def _payload_args(self) -> dict[str, Any]:
        """The constructor arguments to serialise, validated as JSON-safe (never pickled)."""
        state = dict(self.__dict__)
        validate_serializable(state)
        return state

    async def handle(self) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement async def handle(self).")

    async def failed(self, exc: Exception) -> None:
        """Called once, after the last failed attempt. Override to notify, log, clean up, etc."""

    async def release(self, delay: int | timedelta = 0) -> None:
        """Call from inside `handle()` and `return` to put the job back on the queue on purpose.

        Counts as one attempt: a release past `tries` is dropped instead of being requeued again.
        No-op on the `sync` driver and for `dispatch_sync()` (there is no queue to put it back on).
        """
        self._released = True  # type: ignore[attr-defined]
        self._release_delay = delay  # type: ignore[attr-defined]

    async def dispatch(self, *, delay: int | timedelta | None = None, queue: str | None = None) -> None:
        """Send this job to the queue (or run it inline on the `sync` driver)."""
        from aso.queue.manager import Queue

        await Queue.dispatch(self, delay=delay, queue=queue)

    async def dispatch_sync(self) -> None:
        """Run this job right now, in this process, reusing the caller's database scope."""
        from aso.queue.manager import Queue

        await Queue.dispatch_sync(self)

    def dispatch_after_response(self) -> None:
        """Queue this job to be sent once the current HTTP response has been sent.

        Requires an active request context (`aso.context.current()`); see the build report
        for the exact hook `foundation/stack.py` needs to add to actually drain and send it.
        """
        from aso import context

        ctx = context.require()
        ctx.extras.setdefault("queue.after_response", []).append(self)
