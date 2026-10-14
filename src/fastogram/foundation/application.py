"""`Application.configure(...)...create()`: the boot API (T-06, like Laravel's bootstrap/app.php)."""

from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp

from fastogram.foundation import paths
from fastogram.foundation.exceptions_config import ExceptionsConfig
from fastogram.foundation.middleware_config import MiddlewareConfig

_current: Application | None = None


def current_application() -> Application | None:
    return _current


def app() -> Application:
    if _current is None:
        raise RuntimeError("The application has not been created. Call create_app() first.")
    return _current


class Application:
    """The booted application. One per process (the last `create()` wins)."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.routing: dict[str, Any] = {}
        self.middleware_config = MiddlewareConfig()
        self.exceptions_config = ExceptionsConfig()
        self.booting_callbacks: list[Callable[[Application], Any]] = []
        self.fastapi: FastAPI | None = None
        self.routes: Any = None  # fastogram.routing.RouteRegistry
        self.raise_exceptions = False  # test client: `with_exception_handling(False)`
        from fastogram.exceptions.handler import ExceptionHandler

        self.exception_handler = ExceptionHandler(self.exceptions_config)

    # ------------------------------------------------------------ builder entry

    @classmethod
    def configure(cls, base_path: str | Path | None = None) -> ApplicationBuilder:
        root = paths.set_base_path(base_path) if base_path is not None else paths.base_path()
        return ApplicationBuilder(cls(root))

    # ------------------------------------------------------------ helpers

    def environment(self, *names: str) -> bool | str:
        from fastogram.config import config

        current = config("app.environment", "production")
        if not names:
            return current
        return current in names

    @property
    def debug(self) -> bool:
        from fastogram.config import config

        return bool(config("app.debug", False))

    def group_stack(self, group: str, inner: ASGIApp) -> ASGIApp:
        """Wrap one route's ASGI app with its group's middleware stack."""
        from fastogram.foundation.stack import build_group_stack

        layers = self.middleware_config.web_layers() if group == "web" else self.middleware_config.api_layers()
        return build_group_stack(group, layers, inner, lambda: self.exception_handler, reraise=lambda: self.raise_exceptions)


class ApplicationBuilder:
    def __init__(self, application: Application) -> None:
        self.application = application

    def with_routing(
        self,
        web: str | None = None,
        api: str | None = None,
        console: str | None = None,
        health: str | None = None,
        api_prefix: str = "/api",
    ) -> ApplicationBuilder:
        self.application.routing = {"web": web, "api": api, "console": console, "health": health, "api_prefix": api_prefix}
        return self

    def with_middleware(self, callback: Callable[[MiddlewareConfig], Any]) -> ApplicationBuilder:
        callback(self.application.middleware_config)
        return self

    def with_exceptions(self, callback: Callable[[ExceptionsConfig], Any]) -> ApplicationBuilder:
        callback(self.application.exceptions_config)
        return self

    def booting(self, callback: Callable[[Application], Any]) -> ApplicationBuilder:
        """Run `callback(app)` during `create()`, after config is loaded and before routes are compiled."""
        self.application.booting_callbacks.append(callback)
        return self

    def create(self) -> FastAPI:
        global _current
        application = self.application
        _current = application
        base = application.base_path

        # 1. environment, 2. configuration
        from fastogram.config import load, load_environment

        load_environment(base)
        load(base / "config")
        application.exception_handler.debug = application.debug
        _check_app_key(application)

        # 3. logging
        with contextlib.suppress(ImportError):
            from fastogram.log import configure_logging

            configure_logging()

        # 4. database engine (no connection yet)
        with contextlib.suppress(ImportError):
            from fastogram.database.engine import configure_from_config

            configure_from_config()

        for callback in application.booting_callbacks:
            callback(application)

        # 5. routes: import route files, compile into FastAPI routes
        fastapi_app = FastAPI(
            lifespan=_lifespan,
            exception_handlers={
                StarletteHTTPException: _delegate_to_handler,
                _request_validation_error(): _delegate_to_handler,
            },
            docs_url="/api/docs" if application.debug else None,
            redoc_url=None,
            openapi_url="/api/openapi.json" if application.debug else None,
        )
        fastapi_app.state.fastogram = application
        application.fastapi = fastapi_app

        from fastogram.routing.registry import load_routes

        application.routes = load_routes(application)
        application.routes.compile(application, fastapi_app)

        # 6. global middleware (Starlette adds them outermost-last; we add innermost first)
        from fastogram.foundation.stack import Boundary, instantiate

        global_layers = application.middleware_config.global_layers()
        for layer in reversed(global_layers):
            fastapi_app.add_middleware(_LayerFactory, layer=layer)  # type: ignore[arg-type]
        fastapi_app.add_middleware(  # type: ignore[arg-type]
            Boundary, handler=lambda: application.exception_handler, reraise=lambda: application.raise_exceptions
        )
        del instantiate
        return fastapi_app


class _LayerFactory:
    """Adapts `instantiate()` to Starlette's `add_middleware(cls, **kwargs)` signature."""

    def __new__(cls, app: ASGIApp, layer: Any) -> Any:  # type: ignore[misc]
        from fastogram.foundation.stack import instantiate

        return instantiate(layer, app)


async def _delegate_to_handler(request: Any, exc: Exception) -> Any:
    """FastAPI-level exceptions (HTTPException, RequestValidationError) go to our handler."""
    from fastogram.exceptions.handler import handler

    application = current_application()
    if application is not None and application.raise_exceptions:
        raise exc
    from fastapi.exceptions import RequestValidationError

    if isinstance(exc, RequestValidationError):
        from fastogram.exceptions.types import ValidationException

        errors: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            errors.setdefault(".".join(loc) or "input", []).append(err.get("msg", "Invalid value."))
        exc = ValidationException(errors)
    return await handler().handle(request, exc)


def _request_validation_error() -> type[Exception]:
    from fastapi.exceptions import RequestValidationError

    return RequestValidationError


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    with contextlib.suppress(ImportError):
        from fastogram.database.engine import dispose

        await dispose()


def _check_app_key(application: Application) -> None:
    from fastogram.config import config

    key = config("app.key") or os.environ.get("APP_KEY", "")
    if application.environment() == "production" and not key:
        raise RuntimeError("No application encryption key has been specified. Run `fastogram key:generate`.")


def environment(*names: str) -> bool | str:
    """`environment("local")` → bool; `environment()` → the name (Laravel's app()->environment())."""
    from fastogram.config import config

    current = config("app.environment", os.environ.get("APP_ENV", "production"))
    if not names:
        return current
    return current in names
