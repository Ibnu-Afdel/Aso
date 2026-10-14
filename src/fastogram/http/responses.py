"""Responses and redirects: `redirect()`, `back()`, `abort()` (T-15, T-20).

SEED (spine). The http package task completes T-15: `redirect().route()`, `.intended()`,
`.with_errors()`, `.with_input()`, `.with_fragment()`, `.cookie()`, `response()` helpers,
`abort_if`/`abort_unless` and the JSON encoder.
"""

from __future__ import annotations

from typing import Any, NoReturn
from urllib.parse import urlsplit

from starlette.responses import RedirectResponse as StarletteRedirectResponse

from fastogram import context
from fastogram.exceptions.types import HttpException


class RedirectResponse(StarletteRedirectResponse):
    def __init__(self, url: str, status_code: int = 302, headers: dict[str, str] | None = None) -> None:
        super().__init__(url, status_code=status_code, headers=headers)

    def with_flash(self, key: str | dict[str, Any], value: Any = None) -> RedirectResponse:
        from fastogram.session import session

        items = key if isinstance(key, dict) else {key: value}
        for k, v in items.items():
            session().flash(k, v)
        return self


class Redirector:
    """`redirect()` without a URL: `redirect().route("posts.index")`, `redirect().back()`."""

    def to(self, url: str, status: int = 302) -> RedirectResponse:
        return RedirectResponse(url, status_code=status)

    def route(self, name: str, *params: Any, **kw: Any) -> RedirectResponse:
        from fastogram.routing import route

        return RedirectResponse(route(name, *params, **kw))

    def back(self, fallback: str = "/") -> RedirectResponse:
        return back(fallback)


def redirect(url: str | None = None, status: int = 302) -> Any:
    if url is None:
        return Redirector()
    return RedirectResponse(url, status_code=status)


def back(fallback: str = "/") -> RedirectResponse:
    ctx = context.current()
    if ctx is not None and ctx.request is not None:
        request = ctx.request
        referer = request.headers.get("referer")
        if referer:
            parts = urlsplit(referer)
            if (parts.scheme, parts.netloc) == (request.url.scheme, request.url.netloc):
                return RedirectResponse(parts.path + (f"?{parts.query}" if parts.query else ""))
        if ctx.session is not None:
            previous = ctx.session.get("_previous_url")
            if previous:
                return RedirectResponse(previous)
    return RedirectResponse(fallback)


def abort(status: int, message: str = "", headers: dict[str, str] | None = None) -> NoReturn:
    raise HttpException(status, message, headers)
