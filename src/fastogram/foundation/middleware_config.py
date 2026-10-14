"""`MiddlewareConfig`: what `.with_middleware(fn)` receives (T-11).

Framework layers are referenced by import string so this module does not import every package.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

# Global layers (every request), outermost first. Layer 3 (HandleExceptions) is the boundary
# around the whole stack, added by the stack builder.
GLOBAL_LAYERS: list[Any] = [
    "fastogram.foundation.stack:RequestContextMiddleware",
    "fastogram.http.method_spoofing:MethodSpoofing",
    "fastogram.database.middleware:DatabaseScope",
]

# The `web` group, outermost first. HandleInertiaRequests is appended by the app (T-17).
WEB_LAYERS: list[Any] = [
    "fastogram.session.middleware:StartSession",
    "fastogram.auth.middleware:AuthenticateSession",
    "fastogram.session.forgery:PreventRequestForgery",
]

API_LAYERS: list[Any] = []

# Route-middleware aliases (T-11 table). Resolved lazily.
DEFAULT_ALIASES: dict[str, Any] = {
    "auth": "fastogram.auth.middleware:Authenticate",
    "guest": "fastogram.auth.middleware:RedirectIfAuthenticated",
    "verified": "fastogram.auth.middleware:EnsureEmailIsVerified",
    "password.confirm": "fastogram.auth.middleware:RequirePassword",
    "throttle": "fastogram.rate_limiting.middleware:ThrottleRequests",
    "signed": "fastogram.routing.signed:ValidateSignature",
    "can": "fastogram.auth.middleware:Authorize",
}

# Laravel's default route-middleware priority. "bindings" is the built-in route-model binding step.
DEFAULT_PRIORITY: list[str] = ["auth", "throttle", "bindings", "can"]


class MiddlewareConfig:
    def __init__(self) -> None:
        self.global_append: list[Any] = []
        self.global_prepend: list[Any] = []
        self.groups: dict[str, dict[str, list[Any]]] = {
            "web": {"append": [], "prepend": [], "remove": []},
            "api": {"append": [], "prepend": [], "remove": []},
        }
        self.custom_groups: dict[str, list[Any]] = {}
        self.aliases: dict[str, Any] = dict(DEFAULT_ALIASES)
        self.priority_list: list[str] = list(DEFAULT_PRIORITY)
        self.csrf_except: list[str] = []
        self.csrf_origin_only = False
        self.csrf_allow_same_site = False
        self.guest_redirect: str | Callable[[Any], str] | None = None
        self.user_redirect: str | Callable[[Any], str] | None = None

    # global
    def append(self, *middleware: Any) -> MiddlewareConfig:
        self.global_append.extend(_flatten(middleware))
        return self

    def prepend(self, *middleware: Any) -> MiddlewareConfig:
        self.global_prepend[:0] = _flatten(middleware)
        return self

    # groups
    def web(self, append: Iterable[Any] = (), prepend: Iterable[Any] = (), remove: Iterable[Any] = ()) -> MiddlewareConfig:
        return self._group("web", append, prepend, remove)

    def api(self, append: Iterable[Any] = (), prepend: Iterable[Any] = (), remove: Iterable[Any] = ()) -> MiddlewareConfig:
        return self._group("api", append, prepend, remove)

    def _group(self, name: str, append: Iterable[Any], prepend: Iterable[Any], remove: Iterable[Any]) -> MiddlewareConfig:
        group = self.groups[name]
        group["append"].extend(append)
        group["prepend"][:0] = list(prepend)
        group["remove"].extend(remove)
        return self

    def group(self, name: str, middleware: Iterable[Any]) -> MiddlewareConfig:
        """A custom group: an alias that expands into several route middleware."""
        self.custom_groups[name] = list(middleware)
        return self

    def alias(self, aliases: dict[str, Any]) -> MiddlewareConfig:
        self.aliases.update(aliases)
        return self

    def priority(self, order: Iterable[str]) -> MiddlewareConfig:
        self.priority_list = list(order)
        return self

    # framework switches
    def prevent_request_forgery(self, except_: Iterable[str] = (), origin_only: bool = False, allow_same_site: bool = False) -> MiddlewareConfig:
        self.csrf_except.extend(except_)
        self.csrf_origin_only = origin_only
        self.csrf_allow_same_site = allow_same_site
        return self

    def redirect_guests_to(self, target: str | Callable[[Any], str]) -> MiddlewareConfig:
        self.guest_redirect = target
        return self

    def redirect_users_to(self, target: str | Callable[[Any], str]) -> MiddlewareConfig:
        self.user_redirect = target
        return self

    # resolved lists (used by the stack builder)
    def web_layers(self) -> list[Any]:
        return self._resolve_group("web", WEB_LAYERS)

    def api_layers(self) -> list[Any]:
        return self._resolve_group("api", API_LAYERS)

    def _resolve_group(self, name: str, base: list[Any]) -> list[Any]:
        group = self.groups[name]
        removed = {_key(m) for m in group["remove"]}
        layers = [m for m in [*group["prepend"], *base, *group["append"]] if _key(m) not in removed]
        return layers

    def global_layers(self) -> list[Any]:
        return [*self.global_prepend, *GLOBAL_LAYERS, *self.global_append]


def _flatten(items: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if isinstance(item, (list, tuple)):
            out.extend(item)
        else:
            out.append(item)
    return out


def _key(middleware: Any) -> str:
    if isinstance(middleware, str):
        return middleware.split(":")[-1]
    return getattr(middleware, "__name__", repr(middleware))
