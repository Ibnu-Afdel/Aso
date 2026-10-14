"""`DatabaseScope`: global layer 2, a fresh lazy unit of work per request (T-06, T-30)."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from fastogram.database.scope import open_scope


class DatabaseScope:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        async with open_scope(fresh=True):
            await self.app(scope, receive, send)
