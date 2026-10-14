"""A domain exception with its own `report()`/`render()` (T-20 "Exceptions that render themselves")."""

from __future__ import annotations

from typing import Any


class PaymentDeclined(Exception):
    def __init__(self, user_message: str = "Payment was declined.") -> None:
        super().__init__(user_message)
        self.user_message = user_message

    def report(self) -> bool:
        return False  # never logged, like `dont_report`

    def render(self, request: Any) -> Any:
        from fastogram.http import back

        return back().with_flash("error", self.user_message)
