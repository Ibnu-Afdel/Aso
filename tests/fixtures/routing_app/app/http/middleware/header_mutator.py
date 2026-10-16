from __future__ import annotations

from aso.http import Middleware, Next, Request, Response


class HeaderMutator(Middleware):
    """Calls `next()`, then mutates the response headers (T-11 "Before and after")."""

    async def handle(self, request: Request, next: Next) -> Response:
        response = await next(request)
        response.headers["X-Mutated"] = "yes"
        return response
