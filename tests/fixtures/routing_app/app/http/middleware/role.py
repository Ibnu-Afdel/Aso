from __future__ import annotations

from aso.http import Middleware, Next, Request, Response, abort


class RequireRole(Middleware):
    """Route middleware with parameters: `.middleware("role:editor,admin")` (T-11)."""

    async def handle(self, request: Request, next: Next, *roles: str) -> Response:
        role = request.header("X-Role")
        if role not in roles:
            abort(403, "Role not allowed.")
        return await next(request)
