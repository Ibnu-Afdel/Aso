"""Method spoofing (T-10): a POST with `_method` or `X-HTTP-Method-Override` becomes PUT/PATCH/DELETE.

SEED (spine): header form only. The http package task adds the `_method` form field (read through
the shared body cache) and limits it to non-API paths.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED = {"PUT", "PATCH", "DELETE"}


class MethodSpoofing:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST":
            for name, value in scope.get("headers", []):
                if name == b"x-http-method-override":
                    method = value.decode("latin-1").upper()
                    if method in ALLOWED:
                        scope["method"] = method
                    break
        await self.app(scope, receive, send)
