"""Responses and redirects: `redirect()`, `back()`, `response()`, `abort()` (T-15, T-20)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.responses import RedirectResponse as StarletteRedirectResponse

from fastogram import context
from fastogram.exceptions.types import HttpException


class RedirectResponse(StarletteRedirectResponse):
    def __init__(self, url: str, status_code: int = 302, headers: dict[str, str] | None = None) -> None:
        super().__init__(url, status_code=status_code, headers=headers)

    # -- flash data (T-15): all of these write into the session *immediately*

    def with_flash(self, key: str | dict[str, Any], value: Any = None) -> RedirectResponse:
        from fastogram.session import session

        items = key if isinstance(key, dict) else {key: value}
        for k, v in items.items():
            session().flash(k, v)
        return self

    def with_errors(self, errors: dict[str, Any], bag: str = "default") -> RedirectResponse:
        from fastogram.session import session

        normalized = {k: v if isinstance(v, list) else [v] for k, v in errors.items()}
        s = session()
        existing = s.get("errors") or {}
        existing = dict(existing) if isinstance(existing, dict) else {}
        existing[bag] = normalized
        s.flash("errors", existing)
        return self

    def with_input(self) -> RedirectResponse:
        """Flash the current request's already-collected input (T-14), minus
        `config("session.dont_flash")`. If nothing has been read yet, only the query string is
        available (reading the body here would require `await`, impossible in this chain)."""
        from fastogram.config import config
        from fastogram.http.request import _INPUT_KEY

        ctx = context.current()
        if ctx is None or ctx.session is None or ctx.request is None:
            return self
        data = ctx.request.scope.get(_INPUT_KEY)
        if data is None:
            data = dict(ctx.request.query_params)
        dont_flash = set(config("session.dont_flash", ["password", "password_confirmation", "current_password"]))
        ctx.session.flash("_old_input", {k: v for k, v in data.items() if k not in dont_flash})
        return self

    def with_fragment(self, fragment: str) -> RedirectResponse:
        """Append `#fragment` to the `Location` header. `HandleInertiaRequests` (T-16/T-17) turns
        a fragment redirect into a `409` for Inertia visits."""
        location = self.headers.get("location", "")
        self.headers["location"] = f"{location}#{fragment}"
        return self

    # -- cookies

    def cookie(
        self,
        key: str,
        value: str = "",
        minutes: int = 0,
        path: str = "/",
        domain: str | None = None,
        secure: bool | None = None,
        http_only: bool = True,
        same_site: str = "lax",
    ) -> RedirectResponse:
        if secure is None:
            secure = _is_https()
        max_age = int(minutes * 60) if minutes else None
        self.set_cookie(
            key=key, value=str(value), max_age=max_age, path=path, domain=domain,
            secure=secure, httponly=http_only, samesite=same_site,  # type: ignore[arg-type]
        )
        return self

    def without_cookie(self, key: str, path: str = "/", domain: str | None = None) -> RedirectResponse:
        self.delete_cookie(key=key, path=path, domain=domain)
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

    def intended(self, default: str = "/") -> RedirectResponse:
        ctx = context.current()
        target = default
        if ctx is not None and ctx.session is not None:
            stored = ctx.session.get("url.intended")
            if stored:
                target = stored
                ctx.session.forget("url.intended")
        return RedirectResponse(target)

    def away(self, url: str, status: int = 302) -> RedirectResponse:
        """A redirect to an external URL, used verbatim (no route resolution)."""
        return RedirectResponse(url, status_code=status)


def redirect(url: str | None = None, status: int = 302) -> Any:
    if url is None:
        return Redirector()
    return RedirectResponse(url, status_code=status)


def resolve_previous_url(fallback: str = "/") -> str:
    """`back()`'s target resolution (T-15): same-origin Referer, then `session._previous_url`."""
    ctx = context.current()
    if ctx is not None and ctx.request is not None:
        request = ctx.request
        referer = request.headers.get("referer")
        if referer:
            parts = urlsplit(referer)
            if (parts.scheme, parts.netloc) == (request.url.scheme, request.url.netloc):
                return parts.path + (f"?{parts.query}" if parts.query else "")
        if ctx.session is not None:
            previous = ctx.session.get("_previous_url")
            if previous:
                return previous
    return fallback


def back(fallback: str = "/") -> RedirectResponse:
    return RedirectResponse(resolve_previous_url(fallback))


# ---------------------------------------------------------------- response() helper


class ResponseBuilder:
    """`response()`: `.json`, `.download`, `.file`, `.stream`, `.no_content` (T-15)."""

    def json(self, data: Any = None, status: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
        from fastogram.http.encoding import jsonable

        return JSONResponse(jsonable(data), status_code=status, headers=headers)

    def no_content(self, status: int = 204) -> Response:
        return Response(status_code=status)

    def download(self, path: str | Path, name: str | None = None, headers: dict[str, str] | None = None) -> FileResponse:
        return FileResponse(path, filename=name or Path(path).name, headers=headers, content_disposition_type="attachment")

    def file(self, path: str | Path, headers: dict[str, str] | None = None) -> FileResponse:
        return FileResponse(path, headers=headers, content_disposition_type="inline")

    def stream(
        self,
        generator: Iterator[Any] | AsyncIterator[Any],
        media_type: str | None = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> StreamingResponse:
        return StreamingResponse(generator, status_code=status, media_type=media_type, headers=headers)


def response() -> ResponseBuilder:
    return ResponseBuilder()


# ---------------------------------------------------------------- abort


def abort(status: int, message: str = "", headers: dict[str, str] | None = None) -> NoReturn:
    raise HttpException(status, message, headers)


def abort_if(condition: bool, status: int, message: str = "", headers: dict[str, str] | None = None) -> None:
    if condition:
        abort(status, message, headers)


def abort_unless(condition: bool, status: int, message: str = "", headers: dict[str, str] | None = None) -> None:
    if not condition:
        abort(status, message, headers)


def _is_https() -> bool:
    from fastogram.config import config

    return str(config("app.url") or "").startswith("https://")
