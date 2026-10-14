"""Reads the request body in middleware, to prove the body cache lets the controller read it too
(T-11, T-14)."""

from __future__ import annotations

from fastogram.http import Middleware, Next, Request, Response

PEEK: list[str] = []


class BodyPeek(Middleware):
    async def handle(self, request: Request, next: Next) -> Response:
        value = await request.input("x")
        PEEK.append(f"peek:{value}")
        return await next(request)
