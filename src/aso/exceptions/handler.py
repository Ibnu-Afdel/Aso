"""The exception handler (T-20): report, then render, then `respond` callbacks.

Completes the SEED left by the spine: the debug page (`aso.exceptions.debug`), the Inertia
error page with shared data even when the exception happened before `HandleInertiaRequests` ran,
MRO-ordered `render()` callbacks, and routing `report()` through `aso.log` (T-22).
"""

from __future__ import annotations

import inspect
import logging
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import HTMLResponse, JSONResponse, Response

from aso import context
from aso.exceptions.types import (
    HTTP_MESSAGES,
    AuthenticationException,
    AuthorizationException,
    HttpException,
    ModelNotFound,
    PageNotFound,
    ThrottleRequestsException,
    TokenMismatchException,
    ValidationException,
)

if TYPE_CHECKING:
    from starlette.requests import Request

    from aso.foundation.exceptions_config import ExceptionsConfig

logger = logging.getLogger("aso")

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
        from aso.foundation.exceptions_config import ExceptionsConfig

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
        """Log the exception (Laravel's `report($e)`), through `aso.log` (T-22).

        Attaches the request id, URL, method, user id and traceback, plus anything from
        `exceptions.context(...)` callbacks, before any registered `report(type, callback)`
        callback runs. A callback returning `False` stops the default log (like `dont_report`).
        """
        for exc_type, callback in self.config.report_callbacks:
            if isinstance(exc, exc_type):
                if callback(exc) is False:
                    return
        extra: dict[str, Any] = {}
        ctx = context.current()
        if ctx is not None:
            request = ctx.request
            if request is not None:
                extra["url"] = str(request.url)
                extra["method"] = request.method
            from aso.context import UNRESOLVED

            if ctx.user is not None and ctx.user is not UNRESOLVED:
                extra["user_id"] = getattr(ctx.user, "id", None)
            scope = ctx.scope or {}
            request_id = (scope.get("state") or {}).get("request_id")
            if request_id:
                extra["request_id"] = request_id
        for ctx_callback in self.config.context_callbacks:
            extra.update(ctx_callback() or {})
        extra["traceback"] = "".join(traceback.format_exception(exc))

        from aso.log import log

        log.error(f"{type(exc).__name__}: {exc}", exc_info=exc, **extra)

    async def render(self, request: Request, exc: BaseException) -> Response:
        # 1. registered render callbacks, most specific type first (MRO order); first non-None wins
        for callback in _ordered_render_callbacks(self.config.render_callbacks, exc):
            result = _call_render(callback, exc, request)
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                return result
        # 2. the exception's own render(request)
        own = getattr(exc, "render", None)
        if callable(own) and not isinstance(exc, HttpException):
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
            from aso.http.responses import back

            response = back().with_flash("error", "The page expired, please try again.")
            response.status_code = redirect_status
            return response

        if isinstance(exc, AuthenticationException):
            target = exc.redirect_to or self._login_url()
            if wants_json:
                body: dict[str, Any] = {"message": exc.message}
                if target:
                    body["redirect_to"] = target
                return JSONResponse(body, status_code=401)
            from aso.http.responses import redirect

            response = redirect(target)
            response.status_code = redirect_status
            return response

        status, message, headers = self._status_for(exc)
        if wants_json:
            body = {"message": message if status < 500 else "Server Error."}
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
        from aso.http.responses import back, redirect

        ctx = context.current()
        session = ctx.session if ctx is not None else None
        if session is not None:
            bag = request.headers.get("x-inertia-error-bag") or exc.bag
            existing = session.get("errors") or {}
            existing = dict(existing) if isinstance(existing, dict) else {}
            existing[bag] = exc.errors
            session.flash("errors", existing)
            if exc.input is not None:
                from aso.config import config

                dont_flash = set(config("session.dont_flash", ["password", "password_confirmation", "current_password"]))
                session.flash("_old_input", {k: v for k, v in exc.input.items() if k not in dont_flash})
        response = redirect(exc.redirect_to) if exc.redirect_to else back()
        response.status_code = status
        return response

    def _login_url(self) -> str:
        from aso.foundation.application import current_application

        app = current_application()
        target = app.middleware_config.guest_redirect if app is not None else None
        if callable(target):
            target = target(context.current().request if context.current() else None)
        if target:
            return str(target)
        try:
            from aso.routing import route

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
            from aso.inertia import inertia
            from aso.inertia.response import _ensure_page_exists
        except ImportError:
            return None
        try:
            # A missing error page must not turn every error into a second, unhandled one.
            _ensure_page_exists(self.config.error_page_component)
        except PageNotFound:
            logger.warning("Inertia error page [%s] is missing; using the plain HTML error page.", self.config.error_page_component)
            return None
        props: dict[str, Any] = {"status": status}
        if message:
            props["message"] = message
        response = inertia(self.config.error_page_component, props)
        response.status_code = status
        if ctx.inertia is not None:
            return response
        # The exception happened before `HandleInertiaRequests` ran (a global web layer or a
        # route middleware raised before reaching it). Find the app's own middleware so the
        # error page still gets share()/version()/root_view (Inertia-Laravel's withSharedData()).
        standalone = self._standalone_inertia_middleware()
        if standalone is None:
            return response
        previous = ctx.inertia
        ctx.inertia = standalone
        try:
            return await response.build({})
        finally:
            ctx.inertia = previous

    def _standalone_inertia_middleware(self) -> Any:
        from aso.foundation.application import current_application
        from aso.foundation.stack import resolve
        from aso.inertia import InertiaMiddleware

        app = current_application()
        if app is None:
            return None
        found: type[InertiaMiddleware] | None = None
        for layer in app.middleware_config.web_layers():
            obj = resolve(layer)
            if isinstance(obj, type) and issubclass(obj, InertiaMiddleware):
                found = obj  # last one wins, matching how it is appended onto the web stack
        if found is None:
            return None
        return found(_noop_asgi)

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
        from aso.exceptions import debug

        return debug.render(request, exc)

    def _plain_html(self, status: int, message: str) -> str:
        import html

        title = HTTP_MESSAGES.get(status, "Error")
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{status} {html.escape(title)}</title></head><body>"
            f"<h1>{status} | {html.escape(title)}</h1></body></html>"
        )


async def _noop_asgi(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover
    """Placeholder `app` for a standalone `InertiaMiddleware` instance we never actually call."""


def _ordered_render_callbacks(
    callbacks: list[tuple[type[BaseException], Callable[..., Any]]], exc: BaseException
) -> list[Callable[..., Any]]:
    """Callbacks that match `exc`, most specific registered type first (MRO order).

    Ties (two callbacks registered for the same type) keep registration order.
    """
    mro = type(exc).__mro__
    scored = [(mro.index(exc_type), i, cb) for i, (exc_type, cb) in enumerate(callbacks) if exc_type in mro]
    scored.sort(key=lambda t: (t[0], t[1]))
    return [cb for _, _, cb in scored]


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
    from aso.foundation.application import current_application

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
