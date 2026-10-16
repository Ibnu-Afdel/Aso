from __future__ import annotations

from aso.http import Middleware, Next, Request, Response, abort


class Raiser(Middleware):
    """Raises before calling `next()`: the nearest boundary must render it at this depth, while
    outer layers (session saving, cookies) still run on the way out (T-11)."""

    async def handle(self, request: Request, next: Next) -> Response:
        abort(400, "raised in middleware")
