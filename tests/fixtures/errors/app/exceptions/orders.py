"""Domain exceptions used to exercise `ExceptionsConfig.report()` / `.dont_report()`."""

from __future__ import annotations


class DontReportMe(Exception):
    """Registered with `e.dont_report([DontReportMe])`."""


class InvalidOrder(Exception):
    """Registered with `e.report(InvalidOrder, callback)`: the callback runs, then the default log."""

    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} is invalid.")
        self.order_id = order_id


class QuietOrder(Exception):
    """Registered with a report callback that returns `False`: stops the default log."""
