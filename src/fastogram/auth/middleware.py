"""Auth middleware (T-38). SEED (spine): `AuthenticateSession` only marks the user as unresolved.

The auth package task implements user loading from the session, `Authenticate` (alias `auth`),
`RedirectIfAuthenticated` (`guest`), `EnsureEmailIsVerified`, `RequirePassword`, `Authorize` (`can`).
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class AuthenticateSession:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
