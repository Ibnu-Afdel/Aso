"""Building the middleware stack (T-06, T-11).

Layout of one request through a web route (outermost first):

    Starlette ServerErrorMiddleware        (last resort, plain 500)
    Boundary  ── HandleExceptions          (global safety net; renders API errors)
      RequestContextMiddleware             (global 1)
      MethodSpoofing                       (global; before routing so `_method` picks the route)
      DatabaseScope                        (global 2)
      user global middleware
        Starlette router  →  matched route →  route.app, wrapped per route:
          Boundary(StartSession(Boundary(AuthenticateSession(Boundary(PreventRequestForgery(
            Boundary(HandleInertiaRequests(Boundary(route pipeline → endpoint))))))))

Group middleware is wrapped **around each route's ASGI app** (not mounted), so FastAPI keeps one
router and one OpenAPI schema. Unmatched URLs reach the group stacks through catch-all fallback
routes registered last (`/api/{path}` for the api group, `/{path}` for the web group), which is
how an unknown URL still gets the React 404 page with shared data (T-20).

Every layer of a group stack sits inside an exception **boundary**: an exception raised at any
depth is rendered by the exception handler at that depth, so the outer layers (session saving,
cookies) still run on the way out. A boundary only converts before the response has started;
after that it re-raises (Laravel's `Routing\\Pipeline::handleException`).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aso import context

if TYPE_CHECKING:
    from aso.exceptions.handler import ExceptionHandler


def resolve(layer: Any) -> Any:
    """Turn `"pkg.module:Name"` into the object; pass anything else through."""
    if isinstance(layer, str):
        module_name, _, attr = layer.partition(":")
        module = importlib.import_module(module_name)
        return getattr(module, attr)
    return layer


def instantiate(layer: Any, app: ASGIApp, *params: str) -> ASGIApp:
    """Wrap `app` with one middleware layer.

    A subclass of `aso.http.Middleware` (the `handle(request, next)` API) goes through the
    pure-ASGI `HandleAdapter`; anything else must be a pure-ASGI middleware class `cls(app)` or a
    factory `fn(app) -> ASGIApp`.
    """
    obj = resolve(layer)
    from aso.http.middleware import Middleware, adapt

    if isinstance(obj, type) and issubclass(obj, Middleware):
        return adapt(obj, app, *params)
    if params:
        return obj(app, *params)
    return obj(app)


class Boundary:
    """Exception boundary: render exceptions into responses at this depth."""

    def __init__(self, app: ASGIApp, handler: Callable[[], ExceptionHandler], *, reraise: Callable[[], bool] | None = None) -> None:
        self.app = app
        self.handler = handler
        self.reraise = reraise

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            handler = self.handler()
            if started or (self.reraise is not None and self.reraise()):
                if started and handler.should_report(exc):
                    handler.report(exc)
                raise
            request = _request_for(scope, receive)
            response = await handler.handle(request, exc)
            await response(scope, receive, send)


def _request_for(scope: Scope, receive: Receive) -> Any:
    ctx = context.current()
    if ctx is not None and ctx.request is not None:
        return ctx.request
    from aso.http.request import Request

    return Request(scope, receive)


class RequestContextMiddleware:
    """Global layer 1: create the per-request context and the `X-Request-ID` header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        import uuid

        from aso.http.request import Request

        headers = dict(scope.get("headers") or [])
        request_id = headers.get(b"x-request-id", b"").decode("latin-1") or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        ctx = context.RequestContext(scope=scope)
        ctx.request = Request(scope, receive)
        token = context.enter(ctx)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode("latin-1"))]
            await send(message)

        try:
            await self.app(scope, ctx.request.receive_replay(receive), send_with_id)
        finally:
            context.leave(token)


class GroupMarker:
    """Innermost-but-one helper: records which group (web/api) a route belongs to."""

    def __init__(self, app: ASGIApp, group: str) -> None:
        self.app = app
        self.group = group

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ctx = context.current()
        if ctx is not None:
            ctx.group = self.group
        await self.app(scope, receive, send)


def build_group_stack(
    group: str,
    layers: list[Any],
    inner: ASGIApp,
    handler: Callable[[], ExceptionHandler],
    reraise: Callable[[], bool] | None = None,
) -> ASGIApp:
    """`Boundary(L1(Boundary(L2(...Boundary(inner)))))` for one route, outermost layer first."""
    app: ASGIApp = Boundary(inner, handler, reraise=reraise)
    for layer in reversed(layers):
        app = Boundary(instantiate(layer, app), handler, reraise=reraise)
    return GroupMarker(app, group)
