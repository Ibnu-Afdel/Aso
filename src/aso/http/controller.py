"""`Controller` base class and `ControllerMiddleware` (T-13)."""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass
class ControllerMiddleware:
    """One entry of `Controller.middleware()`: `ControllerMiddleware("subscribed", except_=["plans"])`."""

    middleware: Any
    only: Sequence[str] | None = None
    except_: Sequence[str] | None = None


class Controller:
    """Base class for controllers. A new instance is created for every request (T-13)."""

    @staticmethod
    def middleware() -> list[Any]:
        """Middleware aliases/classes/`ControllerMiddleware` entries merged into the route's own
        middleware at compile time. Override as a `@staticmethod` returning a list."""
        return []

    async def authorize(self, ability: str, *args: Any) -> None:
        """Delegates to `aso.auth.Gate` (T-39). Raises `AuthorizationException` -> 403."""
        from aso.auth import Gate  # lazy: the auth package may not define it yet

        result = Gate.authorize(ability, *args)
        if inspect.isawaitable(result):
            await result
