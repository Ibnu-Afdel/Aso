"""The exception handler (T-20): report, then render, then `respond` callbacks.

SEED (spine): correct structure and the core web rules. The errors package task completes it to
the full T-20 spec (debug page, Inertia error page with shared data, `inertia_error_page`, JSON
debug fields, context callbacks, log integration).
"""

from __future__ import annotations

import inspect
import logging
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import HTMLResponse, JSONResponse, Response

from fastogram import context
from fastogram.exceptions.types import (
    HTTP_MESSAGES,
    AuthenticationException,
    AuthorizationException,
    HttpException,
    ModelNotFound,
    ThrottleRequestsException,
    TokenMismatchException,
    ValidationException,
)

if TYPE_CHECKING:
    from starlette.requests import Request

    from fastogram.foundation.exceptions_config import ExceptionsConfig

logger = logging.getLogger("fastogram")

INTERNAL_DONT_REPORT: tuple[type[BaseException], ...] = (
    StarletteHTTPException,
    ModelNotFound,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    TokenMismatchException,
    ThrottleRequestsException,
)


class ExceptionHandler:
    def __init__(self, config: ExceptionsConfig | None = None, debug: bool = False) -> None:
        from fastogram.foundation.exceptions_config import ExceptionsConfig

        self.config = config or ExceptionsConfig()
        self.debug = debug

    # ------------------------------------------------------------ public

    async def handle(self, request: Request, exc: BaseException) -> Response:
        if self.should_report(exc):
            self.report(exc)
        response = await self.render(request, exc)
        for callback in self.config.respond_callbacks:
            result = callback(response, exc, request)
            if inspect.isawaitable(result):
                result = await result
            response = result or response
        return response

    def should_report(self, exc: BaseException) -> bool:
        if isinstance(exc, INTERNAL_DONT_REPORT) or isinstance(exc, tuple(self.config.dont_report_types)):
            return False
        own = getattr(exc, "report", None)
        if callable(own):
            try:
                if own() is False:
                    return False
            except TypeError:
                pass
        return True

    def report(self, exc: BaseException) -> None:
        for exc_type, callback in self.config.report_callbacks:
            if isinstance(exc, exc_type):
                if callback(exc) is False:
                    return
        extra: dict[str, Any] = {}
        for ctx_callback in self.config.context_callbacks:
            extra.update(ctx_callback() or {})
        logger.error("%s: %s", type(exc).__name__, exc, exc_info=exc, extra={"context": extra})

    async def render(self, request: Request, exc: BaseException) -> Response:
        # 1. registered render callbacks (MRO order)
        for exc_type, callback in self.config.render_callbacks:
            if isinstance(exc, exc_type):
                result = _call_render(callback, exc, request)
                if inspect.isawaitable(result):
                    result = await result
                if result is not None:
                    return result
        # 2. the exception's own render(request)
        own = getattr(exc, "render", None)
        if callable(own) and not isinstance(exc, (HttpException,)):
            result = own(request)
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                return result
        # 3. built-in conversions
        return await self._render_builtin(request, exc)

    # ------------------------------------------------------------ built-in rendering

    async def _render_builtin(self, request: Request, exc: BaseException) -> Response:
        wants_json = self.wants_json(request)
        redirect_status = 303 if request.method in ("PUT", "PATCH", "DELETE") else 302

        if isinstance(exc, ValidationException):
            if wants_json:
                return JSONResponse({"message": exc.summary(), "errors": exc.errors}, status_code=422)
            return self._validation_redirect(request, exc, redirect_status)

        if isinstance(exc, TokenMismatchException) and request.headers.get("x-inertia") == "true":
            from fastogram.http.responses import back

            response = back().with_flash("error", "The page expired, please try again.")
            response.status_code = redirect_status
            return response

        if isinstance(exc, AuthenticationException):
            if wants_json:
                return JSONResponse({"message": exc.message}, status_code=401)
            from fastogram.http.responses import redirect

            target = exc.redirect_to or self._login_url()
            response = redirect(target)
            response.status_code = redirect_status
            return response

        status, message, headers = self._status_for(exc)
        if wants_json:
            body: dict[str, Any] = {"message": message if status < 500 else "Server Error."}
            if self.debug:
                body["message"] = str(exc) or message
                body.update(self._debug_fields(exc))
            return JSONResponse(body, status_code=status, headers=headers)
        if self.debug and (status >= 500 or not isinstance(exc, (StarletteHTTPException, ModelNotFound, AuthorizationException))):
            return HTMLResponse(self._debug_html(request, exc), status_code=status, headers=headers)
        inertia_response = await self._inertia_error_page(request, status, message if status < 500 else None)
        if inertia_response is not None:
            for k, v in (headers or {}).items():
                inertia_response.headers[k] = v
            return inertia_response
        return HTMLResponse(self._plain_html(status, message), status_code=status, headers=headers)

    def _status_for(self, exc: BaseException) -> tuple[int, str, dict[str, str] | None]:
        if isinstance(exc, StarletteHTTPException):
            message = exc.detail if isinstance(exc.detail, str) else HTTP_MESSAGES.get(exc.status_code, "")
            return exc.status_code, message, dict(exc.headers or {}) or None
        if isinstance(exc, ModelNotFound):
            return 404, exc.message, None
        if isinstance(exc, AuthorizationException):
            return exc.status_code, exc.message, None
        status = getattr(exc, "status_code", 500)
        if not isinstance(status, int):
            status = 500
        return status, HTTP_MESSAGES.get(status, "Server Error"), None

    def wants_json(self, request: Request) -> bool:
        ctx = context.current()
        if ctx is not None and ctx.group == "api":
            return True
        if request.headers.get("x-inertia") == "true":
            return False
        accept = request.headers.get("accept", "")
        return "application/json" in accept or "+json" in accept

    def _validation_redirect(self, request: Request, exc: ValidationException, status: int) -> Response:
        from fastogram.http.responses import back, redirect

        ctx = context.current()
        session = ctx.session if ctx is not None else None
        if session is not None:
            bag = request.headers.get("x-inertia-error-bag") or exc.bag
            existing = session.get("errors") or {}
            existing = dict(existing) if isinstance(existing, dict) else {}
            existing[bag] = exc.errors
            session.flash("errors", existing)
            if exc.input is not None:
                from fastogram.config import config

                dont_flash = set(config("session.dont_flash", ["password", "password_confirmation", "current_password"]))
                session.flash("_old_input", {k: v for k, v in exc.input.items() if k not in dont_flash})
        response = redirect(exc.redirect_to) if exc.redirect_to else back()
        response.status_code = status
        return response

    def _login_url(self) -> str:
        from fastogram.foundation.application import current_application

        app = current_application()
        target = app.middleware_config.guest_redirect if app is not None else None
        if callable(target):
            target = target(context.current().request if context.current() else None)
        if target:
            return str(target)
        try:
            from fastogram.routing import route

            return route("login")
        except Exception:
            return "/login"

    async def _inertia_error_page(self, request: Request, status: int, message: str | None) -> Response | None:
        ctx = context.current()
        if ctx is None or ctx.group != "web" or ctx.session is None:
            return None
        statuses = self.config.error_page_statuses
        if status not in statuses:
            return None
        try:
            from fastogram.inertia import inertia
        except ImportError:
            return None
        props: dict[str, Any] = {"status": status}
        if message:
            props["message"] = message
        response = inertia(self.config.error_page_component, props)
        response.status_code = status
        return response

    def _debug_fields(self, exc: BaseException) -> dict[str, Any]:
        tb = traceback.extract_tb(exc.__traceback__)
        last = tb[-1] if tb else None
        return {
            "exception": type(exc).__qualname__,
            "file": last.filename if last else None,
            "line": last.lineno if last else None,
            "trace": [{"file": f.filename, "line": f.lineno, "function": f.name} for f in tb],
        }

    def _debug_html(self, request: Request, exc: BaseException) -> str:
        import html

        trace = "".join(traceback.format_exception(exc))
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>"
            f"{html.escape(type(exc).__name__)}</title></head><body style='font-family:monospace'>"
            f"<h1>{html.escape(type(exc).__name__)}</h1><p>{html.escape(str(exc))}</p>"
            f"<p>{html.escape(request.method)} {html.escape(str(request.url))}</p>"
            f"<pre>{html.escape(trace)}</pre></body></html>"
        )

    def _plain_html(self, status: int, message: str) -> str:
        import html

        title = HTTP_MESSAGES.get(status, "Error")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{status} {html.escape(title)}</title></head><body>"
            f"<h1>{status} | {html.escape(title)}</h1></body></html>"
        )


def _call_render(callback: Callable[..., Any], exc: BaseException, request: Request) -> Any:
    try:
        params = len(inspect.signature(callback).parameters)
    except (TypeError, ValueError):
        params = 2
    return callback(exc, request) if params >= 2 else callback(exc)


_handler: ExceptionHandler | None = None


def handler() -> ExceptionHandler:
    """The application's exception handler (a default one before boot)."""
    global _handler
    from fastogram.foundation.application import current_application

    app = current_application()
    if app is not None:
        return app.exception_handler
    if _handler is None:
        _handler = ExceptionHandler()
    return _handler


def report(exc: BaseException) -> None:
    """Report an exception (log it) and carry on, like Laravel's `report($e)`."""
    h = handler()
    if h.should_report(exc):
        h.report(exc)
