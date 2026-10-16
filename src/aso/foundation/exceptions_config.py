"""`ExceptionsConfig`: what `.with_exceptions(fn)` receives (T-20)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

DEFAULT_ERROR_STATUSES = [403, 404, 419, 429, 500, 503]


class ExceptionsConfig:
    def __init__(self) -> None:
        self.report_callbacks: list[tuple[type[BaseException], Callable[[Any], Any]]] = []
        self.render_callbacks: list[tuple[type[BaseException], Callable[..., Any]]] = []
        self.respond_callbacks: list[Callable[..., Any]] = []
        self.context_callbacks: list[Callable[[], dict[str, Any]]] = []
        self.dont_report_types: list[type[BaseException]] = []
        self.error_page_component = "error"
        self.error_page_statuses: list[int] = list(DEFAULT_ERROR_STATUSES)

    def report(self, exc_type: type[BaseException], callback: Callable[[Any], Any]) -> ExceptionsConfig:
        """Run `callback(exc)` when an exception of this type is reported. Return `False` to stop the default log."""
        self.report_callbacks.append((exc_type, callback))
        return self

    def render(self, exc_type: type[BaseException], callback: Callable[..., Any]) -> ExceptionsConfig:
        """Render this exception type yourself: `callback(exc, request)` returns a response or `None`."""
        self.render_callbacks.append((exc_type, callback))
        return self

    def respond(self, callback: Callable[..., Any]) -> ExceptionsConfig:
        """Change every error response: `callback(response, exc, request)` returns a response."""
        self.respond_callbacks.append(callback)
        return self

    def dont_report(self, types: Iterable[type[BaseException]]) -> ExceptionsConfig:
        self.dont_report_types.extend(types)
        return self

    def context(self, callback: Callable[[], dict[str, Any]]) -> ExceptionsConfig:
        """Add data to every report (`{"tenant": ...}`)."""
        self.context_callbacks.append(callback)
        return self

    def inertia_error_page(self, component: str = "error", statuses: Iterable[int] | None = None) -> ExceptionsConfig:
        self.error_page_component = component
        if statuses is not None:
            self.error_page_statuses = list(statuses)
        return self
