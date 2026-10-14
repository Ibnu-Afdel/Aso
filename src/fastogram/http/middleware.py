"""User middleware API: `class X(Middleware): async def handle(self, request, next)` (T-11).

`HandleAdapter` adapts it onto pure ASGI (D-025): the inner app only starts running once
`handle()` actually calls `next(request)` (so a middleware that short-circuits never runs the
rest of the chain), and the response streams through untouched unless `handle()` reads its body.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context

Next = Callable[[Any], Awaitable[Response]]


class Middleware:
    """Base class for user middleware. Subclasses implement `handle(request, next, *params)`."""

    async def handle(self, request: Any, next: Next, *params: str) -> Response:  # pragma: no cover - interface
        return await next(request)


class _LazyResponse:
    """What `next(request)` returns: status + mutable headers available immediately, body read
    lazily from the still-running inner app. Reading it (`materialize()`) buffers the body;
    leaving it alone lets `HandleAdapter` stream the body through untouched."""

    def __init__(self, status_code: int, raw_headers: list[tuple[bytes, bytes]], queue: asyncio.Queue[Message], task: asyncio.Task[None]) -> None:
        self.status_code = status_code
        self.raw_headers = raw_headers
        self._queue = queue
        self._task = task
        self._chunks: list[bytes] | None = None

    @property
    def headers(self) -> MutableHeaders:
        return MutableHeaders(raw=self.raw_headers)

    @property
    def touched(self) -> bool:
        return self._chunks is not None

    async def materialize(self) -> bytes:
        if self._chunks is None:
            chunks: list[bytes] = []
            while True:
                message = await self._queue.get()
                if message["type"] == "__done__":
                    self._raise_if_failed()
                    break
                if message["type"] == "http.response.body":
                    chunks.append(message.get("body", b""))
            self._chunks = chunks
        return b"".join(self._chunks)

    async def stream_to(self, send: Send) -> None:
        while True:
            message = await self._queue.get()
            if message["type"] == "__done__":
                self._raise_if_failed()
                break
            await send(message)

    def _raise_if_failed(self) -> None:
        if self._task.done():
            exc = self._task.exception()
            if exc is not None:
                raise exc

    def cancel(self) -> None:
        if not self._task.done():
            self._task.cancel()


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
        pending: list[_LazyResponse] = []

        async def call_next(_request: Any) -> _LazyResponse:
            queue: asyncio.Queue[Message] = asyncio.Queue()
            start_event = asyncio.Event()
            started: dict[str, Any] = {}

            async def inner_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    started["status"] = message["status"]
                    started["headers"] = list(message.get("headers", []))
                    start_event.set()
                else:
                    await queue.put(message)

            async def run_inner() -> None:
                try:
                    await self.app(scope, receive, inner_send)
                finally:
                    await queue.put({"type": "__done__"})
                    start_event.set()

            task = asyncio.ensure_future(run_inner())
            await start_event.wait()
            if "status" not in started:
                await task  # the inner app raised before producing a response: re-raise it here
            lazy = _LazyResponse(started["status"], started["headers"], queue, task)
            pending.append(lazy)
            return lazy

        response = await instance.handle(request, call_next, *self.params)

        if isinstance(response, _LazyResponse) and not response.touched:
            await send({"type": "http.response.start", "status": response.status_code, "headers": response.raw_headers})
            await response.stream_to(send)
        else:
            if isinstance(response, _LazyResponse):
                body = await response.materialize()
                real = Response(content=body, status_code=response.status_code)
                real.raw_headers = response.raw_headers
                response = real
            for lazy in pending:
                if lazy is not response:
                    lazy.cancel()
            await response(scope, receive, send)

        terminate = getattr(instance, "terminate", None)
        if terminate is not None:
            await terminate(request, response)


def adapt(middleware: type[Middleware], app: ASGIApp, *params: str) -> ASGIApp:
    return HandleAdapter(app, middleware, *params)
