"""`clear_history()` (T-16 "History encryption").

Tells the client to throw away its history-encryption key on the next rendered page, making
earlier (encrypted) history entries unreadable. Request-scoped: stored in `context.extras` under
a namespaced key per the `RequestContext` docstring's ownership table.
"""

from __future__ import annotations

from fastogram import context

_FLAG = "inertia.clear_history"


def clear_history() -> None:
    context.require().extras[_FLAG] = True


def consume_clear_history() -> bool:
    """Read-and-leave-set; `InertiaResponse.build()` checks this to emit `clearHistory: true`."""
    ctx = context.current()
    return bool(ctx is not None and ctx.extras.get(_FLAG))
