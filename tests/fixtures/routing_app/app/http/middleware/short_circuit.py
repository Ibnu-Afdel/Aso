from __future__ import annotations

from aso.http import Middleware, Next, Request, Response
from aso.http import response as response_builder


class ShortCircuit(Middleware):
    """Returns its own response without calling `next()`: the inner app must never run (T-11)."""

    async def handle(self, request: Request, next: Next) -> Response:
        return response_builder().json({"short": True})
