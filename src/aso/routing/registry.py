"""Route registry: record definitions, then compile them into FastAPI routes (T-10, T-13, T-21).

Two phases, as T-10 "How it works" describes: `Route.get(...)` (and friends) only append a
`RouteDefinition` to the registry while route files are imported (`load_routes`); nothing touches
FastAPI yet. `RouteRegistry.compile()` (called once by `Application.create()`) then translates
every definition into one or more real FastAPI routes, synthesises their endpoint wrapper
(controller/`FormRequest`/model-binding/path-param classification, T-13), and wraps each route's
ASGI app with its per-route middleware pipeline (T-11) and then its group's stack (T-06).
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

import inflect
from fastapi import FastAPI
from starlette.responses import JSONResponse, Response

from aso import context
from aso.routing import paths

if TYPE_CHECKING:
    from aso.foundation.application import Application

_inflect = inflect.engine()


@dataclass
class RouteDefinition:
    methods: list[str]
    path: str
    action: Any
    group: str = "web"
    route_name: str | None = None
    middleware_list: list[Any] = field(default_factory=list)
    excluded_middleware: list[Any] = field(default_factory=list)
    wheres: dict[str, str] = field(default_factory=dict)
    is_fallback: bool = False
    model_bindings: list[tuple[str, type, str | None]] = field(default_factory=list)

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

    def where(self, name: str, pattern: str) -> RouteDefinition:
        self.wheres[name] = pattern
        return self

    def where_number(self, name: str) -> RouteDefinition:
        return self.where(name, r"[0-9]+")

    def where_alpha(self, name: str) -> RouteDefinition:
        return self.where(name, r"[a-zA-Z]+")

    def where_uuid(self, name: str) -> RouteDefinition:
        return self.where(name, "__uuid__")

    def controller_action(self) -> tuple[type | None, str | None]:
        controller_cls, _method, method_name = classify_action(self.action)
        return controller_cls, method_name


class RouteRegistry:
    def __init__(self) -> None:
        self.definitions: list[RouteDefinition] = []
        self.external_routers: list[tuple[Any, str, tuple[dict[str, Any], ...]]] = []

    def by_name(self, name: str) -> RouteDefinition | None:
        for d in self.definitions:
            if d.route_name == name:
                return d
        return None

    def compile(self, application: Application, fastapi_app: FastAPI) -> None:
        prefix = application.routing.get("api_prefix", "/api")
        fallback_by_group: dict[str, RouteDefinition] = {}
        for d in self.definitions:
            if d.is_fallback:
                fallback_by_group[d.group] = d
                continue
            _compile_one(application, fastapi_app, d, prefix)
        self._compile_external_routers(application, fastapi_app, prefix)

        health = application.routing.get("health")
        if health:
            async def _health() -> Response:
                return JSONResponse({"status": "up"})

            fastapi_app.router.add_api_route(health, _health, methods=["GET"], include_in_schema=False)

        for group, wildcard in (("api", f"{prefix}/{{path:path}}"), ("web", "/{path:path}")):
            fb = fallback_by_group.get(group)
            if fb is not None:
                _compile_fallback(application, fastapi_app, fb, wildcard, group)
            else:
                _add_fallback(application, fastapi_app, wildcard, group)

    def _compile_external_routers(self, application: Application, fastapi_app: FastAPI, prefix: str) -> None:
        for router, group, groups in self.external_routers:
            route_prefix = "".join(g.get("prefix", "") for g in groups)
            full_prefix = (prefix + route_prefix) if group == "api" else route_prefix
            for source_route in router.routes:
                full_path = full_prefix + source_route.path
                fastapi_app.router.add_api_route(
                    full_path,
                    source_route.endpoint,
                    methods=list(source_route.methods or []),
                    name=source_route.name,
                    include_in_schema=(group == "api"),
                )
                route = fastapi_app.router.routes[-1]
                route.app = application.group_stack(group, route.app)  # type: ignore[attr-defined]


def _add_fallback(application: Application, fastapi_app: FastAPI, path: str, group: str) -> None:
    async def _not_found(path: str) -> Response:
        from aso.http.responses import abort

        abort(404)

    fastapi_app.router.add_api_route(
        path, _not_found, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False
    )
    route = fastapi_app.router.routes[-1]
    route.app = _public_first(group, application.group_stack(group, route.app))  # type: ignore[attr-defined]


def _public_first(group: str, app: Any) -> Any:
    if group != "web":
        return app
    from aso.routing.static import PublicFilesFirst

    return PublicFilesFirst(app)


def _compile_fallback(application: Application, fastapi_app: FastAPI, fb: RouteDefinition, path: str, group: str) -> None:
    endpoint, model_bindings, _types = make_endpoint(fb)
    fb.model_bindings = model_bindings
    fastapi_app.router.add_api_route(
        path, endpoint, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        name=fb.route_name, include_in_schema=False,
    )
    route = fastapi_app.router.routes[-1]
    from aso.routing.pipeline import build_route_pipeline

    pipeline_app = build_route_pipeline(application, fb, route.app)
    route.app = _public_first(group, application.group_stack(group, pipeline_app))  # type: ignore[attr-defined]


# ---------------------------------------------------------------- recording

_registry: contextvars.ContextVar[RouteRegistry | None] = contextvars.ContextVar("aso_routes", default=None)
_group_stack: contextvars.ContextVar[tuple[dict[str, Any], ...]] = contextvars.ContextVar("aso_route_groups", default=())
_current_group: contextvars.ContextVar[str] = contextvars.ContextVar("aso_route_file_group", default="web")
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

    def controller(self, controller_cls: type) -> _PendingGroup:
        self.attrs["controller"] = controller_cls
        return self

    @contextmanager
    def group(self) -> Iterator[None]:
        token = _group_stack.set((*_group_stack.get(), self.attrs))
        try:
            yield
        finally:
            _group_stack.reset(token)


ANY_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class Route:
    """The `Route` facade used in `routes/*.py`."""

    @staticmethod
    def _add(methods: list[str], path: str, action: Any) -> RouteDefinition:
        registry = _registry.get()
        if registry is None:
            raise RuntimeError("Route.get(...) only works inside a route file loaded by create_app().")
        groups = _group_stack.get()
        if isinstance(action, str):
            controller = next((g["controller"] for g in reversed(groups) if "controller" in g), None)
            if controller is None:
                raise RuntimeError(
                    f"Route action {action!r} is a bare string; use it inside "
                    "`with Route.controller(SomeController).group(): ...`."
                )
            action = [controller, action]
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
    def options(path: str, action: Any) -> RouteDefinition:
        return Route._add(["OPTIONS"], path, action)

    @staticmethod
    def match(methods: list[str], path: str, action: Any) -> RouteDefinition:
        return Route._add([m.upper() for m in methods], path, action)

    @staticmethod
    def any(path: str, action: Any) -> RouteDefinition:
        return Route._add(list(ANY_METHODS), path, action)

    @staticmethod
    def redirect(path: str, target: str, status: int = 302) -> RouteDefinition:
        async def _action() -> Any:
            from aso.http.responses import redirect

            return redirect(target, status=status)

        return Route._add(["GET", "HEAD"], path, _action)

    @staticmethod
    def permanent_redirect(path: str, target: str) -> RouteDefinition:
        return Route.redirect(path, target, status=301)

    @staticmethod
    def inertia(path: str, component: str, props: dict[str, Any] | None = None) -> RouteDefinition:
        async def _action() -> Any:
            from aso.inertia import inertia as inertia_response

            return inertia_response(component, props)

        return Route._add(["GET", "HEAD"], path, _action)

    @staticmethod
    def fallback(action: Any) -> RouteDefinition:
        registry = _registry.get()
        if registry is None:
            raise RuntimeError("Route.fallback(...) only works inside a route file loaded by create_app().")
        d = RouteDefinition(methods=list(ANY_METHODS), path="/{__aso_fallback__}", action=action,
                             group=_current_group.get(), is_fallback=True)
        registry.definitions.append(d)
        return d

    @staticmethod
    def resource(name: str, controller: type, *, api: bool = False) -> ResourceRegistration:
        exclude = {"create", "edit"} if api else set()
        return _register_resource(name, controller, exclude)

    @staticmethod
    def api_resource(name: str, controller: type) -> ResourceRegistration:
        return Route.resource(name, controller, api=True)

    @staticmethod
    def middleware(*middleware: Any) -> _PendingGroup:
        return _PendingGroup({}).middleware(*middleware)

    @staticmethod
    def prefix(prefix: str) -> _PendingGroup:
        return _PendingGroup({}).prefix(prefix)

    @staticmethod
    def name(name: str) -> _PendingGroup:
        return _PendingGroup({}).name(name)

    @staticmethod
    def controller(controller_cls: type) -> _PendingGroup:
        return _PendingGroup({}).controller(controller_cls)

    @staticmethod
    def include(file: str) -> None:
        """Load another route file. Its routes inherit the groups currently open."""
        from aso.foundation.application import current_application
        from aso.foundation.paths import base_path

        application = current_application()
        base = application.base_path if application is not None else base_path()
        target = base / file
        runpy.run_path(str(target), run_name=f"routes.{target.stem}")

    @staticmethod
    def include_router(router: Any) -> None:
        """Mount a plain FastAPI `APIRouter`. Inherits the group of the file it is called in."""
        registry = _registry.get()
        if registry is None:
            raise RuntimeError("Route.include_router(...) only works inside a route file loaded by create_app().")
        registry.external_routers.append((router, _current_group.get(), _group_stack.get()))


# ---------------------------------------------------------------- resources


RESOURCE_ACTIONS: list[tuple[str, list[str], str]] = [
    ("index", ["GET", "HEAD"], ""),
    ("create", ["GET", "HEAD"], "/create"),
    ("store", ["POST"], ""),
    ("show", ["GET", "HEAD"], "/{param}"),
    ("edit", ["GET", "HEAD"], "/{param}/edit"),
    ("update", ["PUT", "PATCH"], "/{param}"),
    ("destroy", ["DELETE"], "/{param}"),
]


def _singular(word: str) -> str:
    return _inflect.singular_noun(word) or word


def _resource_segments(resource: str) -> list[tuple[str, str]]:
    return [(part, _singular(part)) for part in resource.split(".")]


class ResourceRegistration:
    def __init__(self, resource: str, segs: list[tuple[str, str]], defs: dict[str, RouteDefinition]) -> None:
        self.resource = resource
        self._segs = segs
        self.defs = defs

    def only(self, *actions: str) -> ResourceRegistration:
        keep = set(actions)
        for name in list(self.defs):
            if name not in keep:
                self._remove(name)
        return self

    def except_(self, *actions: str) -> ResourceRegistration:
        for name in set(actions):
            self._remove(name)
        return self

    def _remove(self, name: str) -> None:
        d = self.defs.pop(name, None)
        if d is not None:
            registry = current_registry()
            if d in registry.definitions:
                registry.definitions.remove(d)

    def names(self, mapping: dict[str, str]) -> ResourceRegistration:
        for action, new_name in mapping.items():
            d = self.defs.get(action)
            if d is not None:
                d.route_name = new_name
        return self

    def parameters(self, mapping: dict[str, str]) -> ResourceRegistration:
        for plural, new_name in mapping.items():
            old = next((s for p, s in self._segs if p == plural), None)
            if old is None:
                continue
            for d in self.defs.values():
                d.path = d.path.replace("{" + old + "}", "{" + new_name + "}")
        return self

    def shallow(self) -> ResourceRegistration:
        if len(self._segs) < 2:
            return self
        last_plural, last_singular = self._segs[-1]
        member = f"/{last_plural}/{{{last_singular}}}"
        for action in ("show", "edit", "update", "destroy"):
            d = self.defs.get(action)
            if d is not None:
                d.path = member + ("/edit" if action == "edit" else "")
        return self

    def middleware(self, *middleware: Any) -> ResourceRegistration:
        for d in self.defs.values():
            d.middleware_list.extend(middleware)
        return self


def _register_resource(resource: str, controller: type, exclude: set[str]) -> ResourceRegistration:
    segs = _resource_segments(resource)
    prefix_parts: list[str] = []
    for plural, singular in segs[:-1]:
        prefix_parts.extend([plural, "{" + singular + "}"])
    last_plural, last_singular = segs[-1]
    collection = "/" + "/".join([*prefix_parts, last_plural]) if prefix_parts else "/" + last_plural
    member = collection + "/{" + last_singular + "}"
    name_prefix = resource

    defs: dict[str, RouteDefinition] = {}
    for action, verbs, suffix in RESOURCE_ACTIONS:
        if action in exclude or not hasattr(controller, action):
            continue
        if suffix == "":
            path = collection
        elif suffix == "/create":
            path = collection + "/create"
        elif suffix == "/{param}":
            path = member
        else:  # "/{param}/edit"
            path = member + "/edit"
        d = Route._add(verbs, path, [controller, action])
        d.name(f"{name_prefix}.{action}")
        defs[action] = d
    return ResourceRegistration(resource, segs, defs)


# ---------------------------------------------------------------- endpoints


def classify_action(action: Any) -> tuple[type | None, Any, str]:
    """`[Controller, "method"]`, an invokable `Controller` subclass, or a bare function."""
    from aso.http.controller import Controller

    if isinstance(action, (list, tuple)):
        controller_cls, method_name = action
        return controller_cls, getattr(controller_cls, method_name), method_name
    if isinstance(action, type) and issubclass(action, Controller):
        return action, action.__call__, "__call__"
    return None, action, getattr(action, "__name__", "action")


def _action_desc(d: RouteDefinition) -> str:
    controller_cls, _method, method_name = classify_action(d.action)
    if controller_cls is not None:
        return f"{controller_cls.__qualname__}.{method_name}"
    return method_name


def make_endpoint(d: RouteDefinition) -> tuple[Any, list[tuple[str, type, str | None]], dict[str, str]]:
    """Build the FastAPI endpoint for one route (T-13): classify every parameter once, at
    compile time, and raise clear errors then."""
    import uuid as _uuid

    from fastapi import Depends

    from aso.database import Model
    from aso.http.request import Request as FgRequest
    from aso.validation.form_request import FormRequest

    controller_cls, method, method_name = classify_action(d.action)
    if not inspect.iscoroutinefunction(method):
        raise RuntimeError(
            f"{_action_desc(d)} must be 'async def'. Aso route handlers are async (T-13)."
        )

    specs = paths.parse_params(d.path)
    path_names = {s.name for s in specs}
    binding_fields = {s.name: s.binding_field for s in specs if s.binding_field}

    hints = typing.get_type_hints(method, include_extras=True)
    sig = inspect.signature(method)
    params = list(sig.parameters.values())
    if controller_cls is not None:
        params = params[1:]  # drop self

    starlette_request_base = FgRequest.__mro__[1]
    request_names: list[str] = []
    new_params: list[inspect.Parameter] = []
    model_bindings_by_name: dict[str, tuple[type, str | None]] = {}
    path_param_types: dict[str, str] = {}

    for p in params:
        ann = hints.get(p.name, p.annotation)
        kind = inspect.Parameter.KEYWORD_ONLY
        if isinstance(ann, type) and issubclass(ann, starlette_request_base):
            request_names.append(p.name)
            continue
        if isinstance(ann, type) and issubclass(ann, FormRequest):
            new_params.append(p.replace(annotation=ann, default=Depends(ann.resolve), kind=kind))
            continue
        if isinstance(ann, type) and issubclass(ann, Model):
            if p.name not in path_names:
                raise RuntimeError(
                    f"{_action_desc(d)}: parameter '{p.name}: {ann.__name__}' has no matching route "
                    f"segment '{{{p.name}}}' in '{d.path}' (route-model binding, T-10)."
                )
            model_bindings_by_name[p.name] = (ann, binding_fields.get(p.name))
            continue
        if p.name in path_names:
            if ann is int:
                path_param_types[p.name] = "int"
            elif ann is _uuid.UUID:
                path_param_types[p.name] = "uuid"
        new_params.append(p.replace(annotation=ann, kind=kind))

    model_bindings = [(s.name, *model_bindings_by_name[s.name]) for s in specs if s.name in model_bindings_by_name]

    async def endpoint(_fg_request: FgRequest, **kwargs: Any) -> Any:
        from aso.http.encoding import to_response

        ctx = context.current()
        request = ctx.request if ctx is not None and ctx.request is not None else _fg_request
        for name in request_names:
            kwargs[name] = request
        for name, _model_cls, _field in model_bindings:
            kwargs[name] = ctx.route_params.get(name) if ctx is not None else None
        if controller_cls is not None:
            result = await method(controller_cls(), **kwargs)
        else:
            result = await method(**kwargs)
        return to_response(result)

    endpoint.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter("_fg_request", inspect.Parameter.KEYWORD_ONLY, annotation=starlette_request_base), *new_params]
    )
    endpoint.__name__ = method_name
    return endpoint, model_bindings, path_param_types


def _ensure_convertor(pattern: str) -> str:
    from starlette.convertors import CONVERTOR_TYPES, Convertor, register_url_convertor

    name = paths.convertor_name(pattern)
    if name not in CONVERTOR_TYPES:
        class _Regex(Convertor[str]):
            regex = pattern

            def convert(self, value: str) -> str:
                return value

            def to_string(self, value: str) -> str:
                return str(value)

        register_url_convertor(name, _Regex())
    return name


def _compile_one(application: Application, fastapi_app: FastAPI, d: RouteDefinition, prefix: str) -> None:
    endpoint, model_bindings, path_param_types = make_endpoint(d)
    d.model_bindings = model_bindings
    clean = paths.clean_path(d.path)

    def type_for(name: str) -> str | None:
        pattern = d.wheres.get(name)
        if pattern is not None:
            return "uuid" if pattern == "__uuid__" else _ensure_convertor(pattern)
        return path_param_types.get(name)

    base_prefix = prefix if d.group == "api" else ""
    include_in_schema = d.group == "api"
    from aso.routing.pipeline import build_route_pipeline

    for variant in paths.compiled_variants(clean, type_for):
        full_path = base_prefix + variant if variant != "/" else (base_prefix or "/")
        fastapi_app.router.add_api_route(
            full_path, endpoint, methods=d.methods, name=d.route_name, include_in_schema=include_in_schema,
        )
        route = fastapi_app.router.routes[-1]
        pipeline_app = build_route_pipeline(application, d, route.app)
        route.app = application.group_stack(d.group, pipeline_app)  # type: ignore[attr-defined]


# ---------------------------------------------------------------- URLs


def route(name: str, params: Any = None, absolute: bool = False, **kw: Any) -> str:
    registry = current_registry()
    d = registry.by_name(name)
    if d is None:
        raise KeyError(f"Route [{name}] not defined.")
    specs = paths.parse_params(d.path)
    values: dict[str, Any] = {}
    if isinstance(params, dict):
        values.update(params)
    elif params is not None and specs:
        first = specs[0]
        if first.binding_field:
            values[first.name] = getattr(params, first.binding_field, params)
        else:
            values[first.name] = getattr(params, "id", params)
    values.update(kw)

    clean = paths.clean_path(d.path)
    url_path, remaining = paths.build_url(clean, values)
    if d.group == "api":
        from aso.foundation.application import current_application

        application = current_application()
        api_prefix = (application.routing.get("api_prefix", "/api") if application is not None else "/api") or "/api"
        url_path = api_prefix + url_path if url_path != "/" else api_prefix
    if remaining:
        url_path += "?" + urlencode(remaining)
    if absolute:
        from aso.routing.url import _to_absolute

        url_path = _to_absolute(url_path)
    return url_path


# ---------------------------------------------------------------- route:list


def route_list(registry: RouteRegistry | None = None) -> list[dict[str, Any]]:
    """Rows for `aso route:list` (method, uri, name, action, middleware)."""
    reg = registry or current_registry()
    from aso.foundation.application import current_application

    application = current_application()
    prefix = (application.routing.get("api_prefix", "/api") if application is not None else "/api") or "/api"
    rows: list[dict[str, Any]] = []
    for d in reg.definitions:
        controller_cls, _method, method_name = classify_action(d.action)
        if controller_cls is not None:
            action_repr = f"{controller_cls.__module__}.{controller_cls.__qualname__}@{method_name}"
        else:
            action_repr = getattr(d.action, "__qualname__", repr(d.action))
        if d.is_fallback:
            uri = f"{prefix}/{{path}}" if d.group == "api" else "/{path}"
        else:
            clean = paths.clean_path(d.path)
            uri = (prefix + clean if clean != "/" else prefix) if d.group == "api" else clean
        rows.append(
            {
                "method": "|".join(d.methods),
                "uri": uri,
                "name": d.route_name or "",
                "action": action_repr,
                "middleware": [_mw_label(m) for m in d.middleware_list],
                "group": d.group,
            }
        )
    return rows


def _mw_label(spec: Any) -> str:
    if isinstance(spec, str):
        return spec
    return getattr(spec, "__name__", repr(spec))
