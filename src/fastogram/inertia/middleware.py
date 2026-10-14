"""`InertiaMiddleware`, the base of the app's `HandleInertiaRequests` (T-17).

Pure ASGI (D-025). Placed last in the `web` group (T-06). Three jobs:

**Inbound:** mark the request as Inertia, check the asset version on GET, store this instance in
the request context so the lazily-built `InertiaResponse` (T-16) can call back into `share()`,
`share_once()`, `version()` and `root_view_for()` at send time.

**Outbound** (Inertia requests only): `302` after `PUT`/`PATCH`/`DELETE` becomes `303`; a redirect
to a URL with a `#fragment` becomes `409` + `X-Inertia-Redirect` (keeps the fragment on a fresh
Inertia GET); `Vary: X-Inertia` is added to every response.
"""

from __future__ import annotations

from typing import Any

from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context
from fastogram.inertia.vite import manifest_hash

REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _header(headers: list[tuple[bytes, bytes]], name: bytes) -> str | None:
    for k, v in headers:
        if k.lower() == name:
            return v.decode("latin-1")
    return None


class InertiaMiddleware:
    """Base of the app's `HandleInertiaRequests`. Override `share()`, `share_once()`, `version()`
    and `root_view_for()`; always start overrides with `**await super().x(request)`."""

    root_view = "app.html"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def version(self, request: Any) -> str:
        return manifest_hash()

    async def share(self, request: Any) -> dict[str, Any]:
        return {}

    async def share_once(self, request: Any) -> dict[str, Any]:
        """Everything returned here is wrapped in `once()` for you (T-17 "Once")."""
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
        headers = request.headers
        is_inertia = headers.get("x-inertia") == "true"
        prefetch = headers.get("purpose") == "prefetch"

        if is_inertia and scope["method"] == "GET":
            current = await self.version(request)
            if headers.get("x-inertia-version", "") != current:
                if ctx.session is not None:
                    ctx.session.reflash()
                response = Response(
                    status_code=409,
                    headers={
                        "X-Inertia-Location": str(request.url),
                        "X-Inertia-Version": current,
                        "Vary": "X-Inertia",
                    },
                )
                await response(scope, receive, send)
                return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = list(message.get("headers", []))

                if is_inertia and not prefetch and status in REDIRECT_STATUSES:
                    location = _header(response_headers, b"location")
                    if location and "#" in location:
                        response_headers = [(k, v) for k, v in response_headers if k.lower() != b"location"]
                        response_headers.append((b"x-inertia-redirect", location.encode("latin-1")))
                        if not any(k.lower() == b"vary" for k, _ in response_headers):
                            response_headers.append((b"vary", b"X-Inertia"))
                        message["status"] = 409
                        message["headers"] = response_headers
                        await send(message)
                        return

                if is_inertia and status == 302 and scope["method"] in ("PUT", "PATCH", "DELETE"):
                    message["status"] = 303

                if not any(k.lower() == b"vary" for k, _ in response_headers):
                    response_headers.append((b"vary", b"X-Inertia"))
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
