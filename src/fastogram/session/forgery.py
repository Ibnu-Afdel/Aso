"""`PreventRequestForgery` (T-12, D-007). SEED (spine): Sec-Fetch-Site + header token.

The session package task completes T-12: `_token` form field via the body cache, `except_`
patterns, `origin_only`, `allow_same_site`, testing bypass + `with_csrf()`, cookie attributes.
"""

from __future__ import annotations

import hmac

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context
from fastogram.exceptions.types import TokenMismatchException

SAFE = {"GET", "HEAD", "OPTIONS"}


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


class PreventRequestForgery:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ctx = context.current()
        if scope["type"] != "http" or ctx is None or ctx.session is None:
            await self.app(scope, receive, send)
            return
        session = ctx.session

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                cookie = f"XSRF-TOKEN={session.token()}; Path=/; SameSite=lax"
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie.encode("latin-1"))]
            await send(message)

        if scope["method"] not in SAFE and _header(scope, b"sec-fetch-site") != "same-origin":
            supplied = _header(scope, b"x-xsrf-token") or _header(scope, b"x-csrf-token") or ""
            if not hmac.compare_digest(supplied.encode(), session.token().encode()):
                raise TokenMismatchException()
        await self.app(scope, receive, send_with_cookie)
