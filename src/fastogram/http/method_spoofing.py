"""Method spoofing (T-10): a POST with `_method` or `X-HTTP-Method-Override` becomes PUT/PATCH/DELETE.

Only for non-API paths (plain HTML forms only post to `routes/web.py`; `routes/api.py` clients
send the real verb). The `_method` form field is read through the shared body cache (T-11), via
the same `fastogram.http.Request` instance every other layer uses, so later reads still work.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED = {"PUT", "PATCH", "DELETE"}


def _header_override(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"x-http-method-override":
            return value.decode("latin-1").upper()
    return None


def _content_type(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"content-type":
            return value.decode("latin-1")
    return ""


def _is_api_path(scope: Scope) -> bool:
    from fastogram.foundation.application import current_application

    application = current_application()
    prefix = (application.routing.get("api_prefix", "/api") if application is not None else "/api") or "/api"
    return str(scope.get("path", "")).startswith(prefix)


class MethodSpoofing:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and not _is_api_path(scope):
            method = _header_override(scope)
            if method is None:
                method = await self._form_override(scope, receive)
            if method in ALLOWED:
                scope["method"] = method
        await self.app(scope, receive, send)

    async def _form_override(self, scope: Scope, receive: Receive) -> str | None:
        if "form" not in _content_type(scope):
            return None
        from fastogram import context
        from fastogram.http.request import Request

        ctx = context.current()
        request = ctx.request if ctx is not None and ctx.request is not None else Request(scope, receive)
        try:
            form = await request.form()
        except Exception:
            return None
        value = form.get("_method")
        return value.upper() if isinstance(value, str) else None
