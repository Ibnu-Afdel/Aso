"""The per-request context (T-06).

One `ContextVar` holds a `RequestContext` for the current HTTP request. Framework layers write
into it (session, user, Inertia state); helpers such as `session()` and `auth()` read from it.
asyncio copies the context for every task, so concurrent requests never share state.

Ownership of the fields:

| field | written by |
|---|---|
| `scope`, `request` | `RequestContextMiddleware` (global layer 1) |
| `group` | the group stack (`"web"` or `"api"`) |
| `session` | `StartSession` (fastogram.session) |
| `user` | `AuthenticateSession` / `auth()` (fastogram.auth) |
| `inertia` | `InertiaMiddleware` (fastogram.inertia) |
| `shared` | `fastogram.inertia.share()` |
| `route`, `route_params` | the route pipeline (fastogram.routing) |
| `extras` | any package, namespaced keys such as `"inertia.clear_history"` |
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

UNRESOLVED: Any = object()
"""Sentinel for `RequestContext.user` before the auth layer has looked the user up."""


@dataclass(eq=False)
class RequestContext:
    scope: dict[str, Any]
    request: Any = None
    group: str | None = None
    session: Any = None
    user: Any = UNRESOLVED
    inertia: Any = None
    shared: dict[str, Any] = field(default_factory=dict)
    route: Any = None
    route_params: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)


_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "fastogram_request_context", default=None
)


def current() -> RequestContext | None:
    """The active request context, or `None` outside an HTTP request (CLI, jobs, tests)."""
    return _current.get()


def require() -> RequestContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("No HTTP request is active. This helper only works during a web or API request.")
    return ctx


def enter(ctx: RequestContext) -> contextvars.Token[RequestContext | None]:
    return _current.set(ctx)


def leave(token: contextvars.Token[RequestContext | None]) -> None:
    _current.reset(token)
