"""A global web-layer middleware that raises *before* `HandleInertiaRequests` runs.

Used to test the exception handler's fallback: when the exception happens before
`ctx.inertia` is set, the handler must still find the app's `HandleInertiaRequests` from
`middleware_config.web_layers()` to supply the error page's shared data (T-20).
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class CrashBeforeInertia:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/crash-before-inertia":
            raise RuntimeError("boom before inertia")
        await self.app(scope, receive, send)
