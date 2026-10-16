"""`PreventRequestForgery` (T-12, D-007): mirrors Laravel 13's `PreventRequestForgery`.

Placed after `StartSession` (needs the session) and before `HandleInertiaRequests` (T-06).

Rendering a mismatch stays in the shared exception handler (T-20): this middleware builds the
exception, not the response. The one wrinkle is the `XSRF-TOKEN` cookie, which must be set on
*every* response, including the error response for a mismatch -- and the `Boundary` wrapping
this middleware (`foundation/stack.py`) renders exceptions with the `send` it was given, not any
wrapper this middleware installs around its own `self.app(...)` call. So a mismatch is rendered
*here*, through the same `handler()` the `Boundary` would have used, rather than re-raised.
"""

from __future__ import annotations

import fnmatch
import hmac
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aso import context
from aso.exceptions.types import HttpException, TokenMismatchException

SAFE = {"GET", "HEAD", "OPTIONS"}


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


def _is_excluded(path: str, full_url: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.startswith("http://") or pattern.startswith("https://"):
            if fnmatch.fnmatch(full_url, pattern):
                return True
        else:
            normalized = pattern if pattern.startswith("/") else f"/{pattern}"
            if fnmatch.fnmatch(path, normalized):
                return True
    return False


def _origin_passes(scope: Scope, allow_same_site: bool) -> bool:
    value = _header(scope, b"sec-fetch-site")
    if value == "same-origin":
        return True
    return bool(allow_same_site and value == "same-site")


def _is_testing() -> bool:
    from aso.config import config

    return config("app.environment") == "testing"


def _force_csrf(scope: Scope) -> bool:
    state = scope.get("state") or {}
    return bool(state.get("aso.force_csrf"))


def _middleware_settings() -> tuple[list[str], bool, bool]:
    from aso.foundation.application import current_application

    application = current_application()
    if application is None:
        return [], False, False
    mw = application.middleware_config
    return list(mw.csrf_except), bool(mw.csrf_origin_only), bool(mw.csrf_allow_same_site)


async def _token_from_body(request: Any) -> str | None:
    """`_token` from a form body, via the shared request input cache (T-11/T-14)."""
    if request is None:
        return None
    try:
        value = await request.input("_token")
    except Exception:
        return None
    return str(value) if value is not None else None


def _xsrf_cookie_header(token: str) -> str:
    from aso.session.configuration import settings

    cfg = settings()
    parts = [f"XSRF-TOKEN={token}", f"Path={cfg.path}", "SameSite=lax"]
    if cfg.domain:
        parts.append(f"Domain={cfg.domain}")
    if cfg.secure:
        parts.append("Secure")
    return "; ".join(parts)


class PreventRequestForgery:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ctx = context.current()
        if ctx is None or ctx.session is None:
            await self.app(scope, receive, send)
            return
        session = ctx.session

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                cookie = _xsrf_cookie_header(session.token())
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie.encode("latin-1"))]
            await send(message)

        try:
            await self._check(scope, ctx, session)
        except HttpException as exc:
            from aso.exceptions.handler import handler

            request = ctx.request
            response = await handler().handle(request, exc)
            await response(scope, receive, send_with_cookie)
            return

        await self.app(scope, receive, send_with_cookie)

    async def _check(self, scope: Scope, ctx: Any, session: Any) -> None:
        method = scope["method"]
        if method in SAFE:
            return

        except_patterns, origin_only, allow_same_site = _middleware_settings()

        request = ctx.request
        path = scope["path"]
        full_url = str(request.url) if request is not None else path
        if _is_excluded(path, full_url, except_patterns):
            return

        if _is_testing() and not _force_csrf(scope):
            return

        if _origin_passes(scope, allow_same_site):
            return
        if origin_only:
            raise HttpException(403, "Forbidden.")

        supplied = (
            _header(scope, b"x-xsrf-token")
            or _header(scope, b"x-csrf-token")
            or await _token_from_body(request)
            or ""
        )
        if not hmac.compare_digest(supplied.encode(), session.token().encode()):
            raise TokenMismatchException()
