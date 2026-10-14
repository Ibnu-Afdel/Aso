"""Test-only middleware: records call order for the middleware-pipeline tests (T-11).

`RECORD` is a module-level list the tests clear before each request and inspect after.
"""

from __future__ import annotations

from fastogram.http import Middleware, Next, Request, Response

RECORD: list[str] = []


class RecordA(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        RECORD.append("before:a")
        response = await next(request)
        RECORD.append("after:a")
        return response

    async def terminate(self, request: Request, response: Response) -> None:
        RECORD.append("terminate:a")


class RecordB(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        RECORD.append("before:b")
        response = await next(request)
        RECORD.append("after:b")
        return response


class RecordC(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        RECORD.append("before:c")
        response = await next(request)
        RECORD.append("after:c")
        return response


class RecordD(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        RECORD.append("before:d")
        response = await next(request)
        RECORD.append("after:d")
        return response
