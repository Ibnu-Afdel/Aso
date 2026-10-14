"""User middleware API: `class X(Middleware): async def handle(self, request, next)` (T-11).

SEED (spine): a working `HandleAdapter` that buffers the inner response. The http package task
completes streaming pass-through, `terminate()`, and response objects that keep headers mutable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context

Next = Callable[[Any], Awaitable[Response]]


class Middleware:
    """Base class for user middleware. Subclasses implement `handle(request, next, *params)`."""

    async def handle(self, request: Any, next: Next, *params: str) -> Response:  # pragma: no cover - interface
        return await next(request)


class HandleAdapter:
    def __init__(self, app: ASGIApp, middleware: type[Middleware], *params: str) -> None:
        self.app = app
        self.middleware_class = middleware
        self.params = params

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from fastogram.http.request import Request

        ctx = context.current()
        request = ctx.request if ctx is not None and ctx.request is not None else Request(scope, receive)
        instance = self.middleware_class()

        async def call_next(_request: Any) -> Response:
            status = 500
            headers: list[tuple[bytes, bytes]] = []
            chunks: list[bytes] = []

            async def capture(message: Message) -> None:
                nonlocal status, headers
                if message["type"] == "http.response.start":
                    status = message["status"]
                    headers = list(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    chunks.append(message.get("body", b""))

            await self.app(scope, receive, capture)
            response = Response(content=b"".join(chunks), status_code=status)
            response.raw_headers = headers
            return response

        response = await instance.handle(request, call_next, *self.params)
        await response(scope, receive, send)
        terminate = getattr(instance, "terminate", None)
        if terminate is not None:
            await terminate(request, response)


def adapt(middleware: type[Middleware], app: ASGIApp, *params: str) -> ASGIApp:
    return HandleAdapter(app, middleware, *params)
