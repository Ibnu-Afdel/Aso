"""`InertiaMiddleware`, the base of the app's `HandleInertiaRequests` (T-17), proven by S-1.

SEED (spine): version 409 with reflash, 302→303, Vary. The inertia package task completes the
fragment 409, `share_once`, manifest hash caching by mtime, prefetch rules.
"""

from __future__ import annotations

import hashlib
from typing import Any

from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context
from fastogram.foundation.paths import public_path


class InertiaMiddleware:
    root_view = "app.html"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def version(self, request: Any) -> str:
        manifest = public_path("build", "manifest.json")
        if public_path("hot").exists() or not manifest.exists():
            return ""
        return hashlib.md5(manifest.read_bytes()).hexdigest()

    async def share(self, request: Any) -> dict[str, Any]:
        return {}

    async def root_view_for(self, request: Any) -> str:
        return self.root_view

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ctx = context.current()
        if scope["type"] != "http" or ctx is None:
            await self.app(scope, receive, send)
            return
        ctx.inertia = self
        request = ctx.request
        is_inertia = request.headers.get("x-inertia") == "true"
        if is_inertia and scope["method"] == "GET":
            current = await self.version(request)
            if request.headers.get("x-inertia-version", "") != current:
                if ctx.session is not None:
                    ctx.session.reflash()
                response = Response(
                    status_code=409,
                    headers={"X-Inertia-Location": str(request.url), "X-Inertia-Version": current, "Vary": "X-Inertia"},
                )
                await response(scope, receive, send)
                return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if is_inertia and message["status"] == 302 and scope["method"] in ("PUT", "PATCH", "DELETE"):
                    message["status"] = 303
                if not any(k == b"vary" for k, _ in headers):
                    headers.append((b"vary", b"X-Inertia"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
