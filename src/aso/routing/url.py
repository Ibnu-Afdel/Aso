"""`url()` and `url().current()/previous()/signed_route()/temporary_signed_route()` (T-21)."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from aso import context
from aso.routing.signed import sign_url


def _app_url() -> str:
    from aso.config import config

    return str(config("app.url") or "http://localhost").rstrip("/")


def _to_absolute(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return _app_url() + path


class Url:
    """`url()` without a path: `url().current()`, `url().signed_route(...)`."""

    def current(self) -> str:
        ctx = context.current()
        if ctx is None or ctx.request is None:
            return _app_url()
        request = ctx.request
        return f"{request.url.scheme}://{request.url.netloc}{request.url.path}"

    def previous(self, fallback: str = "/") -> str:
        from aso.http.responses import resolve_previous_url

        return resolve_previous_url(fallback)

    def signed_route(self, name: str, params: dict[str, Any] | None = None) -> str:
        from aso.routing.registry import route as route_fn

        base = route_fn(name, params or {}, absolute=True)
        return sign_url(base)

    def temporary_signed_route(
        self,
        name: str,
        expires: timedelta | int | float,
        params: dict[str, Any] | None = None,
    ) -> str:
        from aso.routing.registry import route as route_fn

        seconds = expires.total_seconds() if isinstance(expires, timedelta) else expires
        base = route_fn(name, params or {}, absolute=True)
        return sign_url(base, expires=int(time.time() + seconds))


def url(path: str | None = None) -> Any:
    """`url("/posts")` -> an absolute URL under `APP_URL`. `url()` -> the `Url` helper object."""
    if path is None:
        return Url()
    return _to_absolute(path)
