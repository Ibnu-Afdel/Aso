"""Route registry: record definitions, then compile them into FastAPI routes (T-10).

SEED (spine): verbs, names, simple groups, controller endpoints with FormRequest injection,
catch-all fallbacks, `route()`. The routing package task completes T-10/T-13/T-21 (resources,
prefix/name groups, wheres and convertors, model binding step, route middleware pipeline with
aliases/params/priority, `Route.inertia`, redirects, include, `route:list` data, signed URLs).
"""

from __future__ import annotations

import contextvars
import inspect
import runpy
import typing
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.params import Depends as DependsParam
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from fastogram import context

if TYPE_CHECKING:
    from fastogram.foundation.application import Application


@dataclass
class RouteDefinition:
    methods: list[str]
    path: str
    action: Any
    group: str = "web"
    route_name: str | None = None
    middleware_list: list[Any] = field(default_factory=list)
    excluded_middleware: list[Any] = field(default_factory=list)

    def name(self, name: str) -> RouteDefinition:
        prefix = "".join(g.get("as", "") for g in _group_stack.get())
        self.route_name = prefix + name
        return self

    def middleware(self, *middleware: Any) -> RouteDefinition:
        self.middleware_list.extend(middleware)
        return self

    def without_middleware(self, *middleware: Any) -> RouteDefinition:
        self.excluded_middleware.extend(middleware)
        return self


class RouteRegistry:
    def __init__(self) -> None:
        self.definitions: list[RouteDefinition] = []

    def by_name(self, name: str) -> RouteDefinition | None:
        for d in self.definitions:
            if d.route_name == name:
                return d
        return None

    def compile(self, application: Application, fastapi_app: FastAPI) -> None:
        prefix = application.routing.get("api_prefix", "/api")
        for d in self.definitions:
            path = (prefix + d.path if d.group == "api" else d.path) or "/"
            endpoint = make_endpoint(d)
            fastapi_app.router.add_api_route(
                path,
                endpoint,
                methods=d.methods,
                name=d.route_name,
                include_in_schema=d.group == "api",
            )
            route = fastapi_app.router.routes[-1]
            route.app = application.group_stack(d.group, route.app)  # type: ignore[attr-defined]
        health = application.routing.get("health")
        if health:
            async def _health() -> Response:
                return JSONResponse({"status": "up"})

            fastapi_app.router.add_api_route(health, _health, methods=["GET"], include_in_schema=False)
        _add_fallback(application, fastapi_app, f"{prefix}/{{path:path}}", "api")
        _add_fallback(application, fastapi_app, "/{path:path}", "web")


def _add_fallback(application: Application, fastapi_app: FastAPI, path: str, group: str) -> None:
    async def _not_found(path: str) -> Response:
        from fastogram.http.responses import abort

        abort(404)

    fastapi_app.router.add_api_route(
        path, _not_found, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False
    )
    route = fastapi_app.router.routes[-1]
    route.app = application.group_stack(group, route.app)  # type: ignore[attr-defined]


# ---------------------------------------------------------------- recording

_registry: contextvars.ContextVar[RouteRegistry | None] = contextvars.ContextVar("fastogram_routes", default=None)
_group_stack: contextvars.ContextVar[tuple[dict[str, Any], ...]] = contextvars.ContextVar("fastogram_route_groups", default=())
_current_group: contextvars.ContextVar[str] = contextvars.ContextVar("fastogram_route_file_group", default="web")
_last_registry: RouteRegistry | None = None


def current_registry() -> RouteRegistry:
    reg = _registry.get() or _last_registry
    if reg is None:
        raise RuntimeError("Routes are not loaded. Create the application first.")
    return reg


def load_routes(application: Application) -> RouteRegistry:
    """Run the route files (fresh each time, so `create_app()` may be called repeatedly)."""
    global _last_registry
    registry = RouteRegistry()
    token = _registry.set(registry)
    try:
        for group in ("web", "api"):
            file = application.routing.get(group)
            if not file:
                continue
            path = application.base_path / file
            if not path.exists():
                continue
            gtoken = _current_group.set(group)
            try:
                runpy.run_path(str(path), run_name=f"routes.{path.stem}")
            finally:
                _current_group.reset(gtoken)
    finally:
        _registry.reset(token)
    _last_registry = registry
    return registry


class _PendingGroup:
    def __init__(self, attrs: dict[str, Any]) -> None:
        self.attrs = attrs

    def middleware(self, *middleware: Any) -> _PendingGroup:
        self.attrs.setdefault("middleware", []).extend(middleware)
        return self

    def prefix(self, prefix: str) -> _PendingGroup:
        self.attrs["prefix"] = self.attrs.get("prefix", "") + "/" + prefix.strip("/")
        return self

    def name(self, name: str) -> _PendingGroup:
        self.attrs["as"] = self.attrs.get("as", "") + name
        return self

    @contextmanager
    def group(self) -> Iterator[None]:
        token = _group_stack.set((*_group_stack.get(), self.attrs))
        try:
            yield
        finally:
            _group_stack.reset(token)


class Route:
    """The `Route` facade used in `routes/*.py`."""

    @staticmethod
    def _add(methods: list[str], path: str, action: Any) -> RouteDefinition:
        registry = _registry.get()
        if registry is None:
            raise RuntimeError("Route.get(...) only works inside a route file loaded by create_app().")
        groups = _group_stack.get()
        prefix = "".join(g.get("prefix", "") for g in groups)
        full = (prefix + "/" + path.strip("/")).rstrip("/") or "/"
        d = RouteDefinition(methods=methods, path=full, action=action, group=_current_group.get())
        for g in groups:
            d.middleware_list.extend(g.get("middleware", []))
        registry.definitions.append(d)
        return d

    @staticmethod
    def get(path: str, action: Any) -> RouteDefinition:
        return Route._add(["GET", "HEAD"], path, action)

    @staticmethod
    def post(path: str, action: Any) -> RouteDefinition:
        return Route._add(["POST"], path, action)

    @staticmethod
    def put(path: str, action: Any) -> RouteDefinition:
        return Route._add(["PUT"], path, action)

    @staticmethod
    def patch(path: str, action: Any) -> RouteDefinition:
        return Route._add(["PATCH"], path, action)

    @staticmethod
    def delete(path: str, action: Any) -> RouteDefinition:
        return Route._add(["DELETE"], path, action)

    @staticmethod
    def middleware(*middleware: Any) -> _PendingGroup:
        return _PendingGroup({}).middleware(*middleware)

    @staticmethod
    def prefix(prefix: str) -> _PendingGroup:
        return _PendingGroup({}).prefix(prefix)

    @staticmethod
    def name(name: str) -> _PendingGroup:
        return _PendingGroup({}).name(name)


# ---------------------------------------------------------------- endpoints


def make_endpoint(d: RouteDefinition) -> Any:
    from fastapi import Depends

    from fastogram.http.request import Request as FgRequest
    from fastogram.validation.form_request import FormRequest

    if callable(d.action) and not isinstance(d.action, (list, tuple)):
        controller_cls, method = None, d.action
    else:
        controller_cls, method_name = d.action
        method = getattr(controller_cls, method_name)
    hints = typing.get_type_hints(method, include_extras=True)
    sig = inspect.signature(method)
    params = list(sig.parameters.values())
    if controller_cls is not None:
        params = params[1:]  # self
    request_names: list[str] = []
    new_params = []
    for p in params:
        ann = hints.get(p.name, p.annotation)
        kind = inspect.Parameter.KEYWORD_ONLY
        if isinstance(ann, type) and issubclass(ann, FormRequest):
            new_params.append(p.replace(annotation=ann, default=Depends(ann.resolve), kind=kind))
        elif isinstance(ann, type) and issubclass(ann, FgRequest.__mro__[1]):  # starlette Request or subclass
            request_names.append(p.name)
        else:
            default = p.default
            if isinstance(default, DependsParam):
                pass
            new_params.append(p.replace(annotation=ann, kind=kind))

    async def endpoint(_fg_request: FgRequest, **kwargs: Any) -> Any:
        ctx = context.current()
        request = ctx.request if ctx is not None and ctx.request is not None else _fg_request
        for name in request_names:
            kwargs[name] = request
        if controller_cls is not None:
            result = method(controller_cls(), **kwargs)
        else:
            result = method(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return to_response(result)

    endpoint.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter("_fg_request", inspect.Parameter.KEYWORD_ONLY, annotation=FgRequest.__mro__[1]), *new_params]
    )
    endpoint.__name__ = getattr(method, "__name__", "endpoint")
    return endpoint


def to_response(result: Any) -> Any:
    if isinstance(result, Response):
        return result
    if result is None:
        return Response(status_code=204)
    from fastapi.encoders import jsonable_encoder

    return JSONResponse(jsonable_encoder(result))


# ---------------------------------------------------------------- URLs


def route(name: str, params: Any = None, absolute: bool = False, **kw: Any) -> str:
    registry = current_registry()
    d = registry.by_name(name)
    if d is None:
        raise KeyError(f"Route [{name}] not defined.")
    values: dict[str, Any] = {}
    if isinstance(params, dict):
        values.update(params)
    elif params is not None:
        import re

        names = re.findall(r"\{(\w+)[^}]*\}", d.path)
        if names:
            values[names[0]] = getattr(params, "id", params)
    values.update(kw)
    path = d.path
    import re

    for key in re.findall(r"\{(\w+)[^}]*\}", path):
        if key in values:
            path = re.sub(r"\{" + key + r"[^}]*\}", str(values.pop(key)), path)
    if d.group == "api":
        path = "/api" + path
    if values:
        path += "?" + urlencode(values)
    return path


def _unused(app: ASGIApp) -> None:  # keep import used for typing tools
    del app
