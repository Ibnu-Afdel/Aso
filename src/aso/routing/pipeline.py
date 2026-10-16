"""The per-route middleware pipeline: aliases, parameters, priority, route-model binding (T-10 §3, T-11).

Built once per route at compile time (`aso.foundation.application.Application.create()`),
not per request. Each layer sits inside its own exception `Boundary` (T-06), so a failure at any
depth of the pipeline is rendered by the nearest boundary, exactly like the group stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from starlette.types import ASGIApp, Receive, Scope, Send

from aso import context

if TYPE_CHECKING:
    from aso.foundation.application import Application
    from aso.routing.registry import RouteDefinition


@dataclass
class _Item:
    key: str
    target: Any
    params: tuple[str, ...]


def _parse_spec(spec: Any) -> tuple[str, tuple[str, ...]]:
    if isinstance(spec, str):
        name, _, rest = spec.partition(":")
        params = tuple(p for p in rest.split(",") if p != "") if rest else ()
        return name, params
    return getattr(spec, "__name__", repr(spec)), ()


def _expand(application: Application, spec: Any, _seen: frozenset[str] = frozenset()) -> list[_Item]:
    name, params = _parse_spec(spec)
    config = application.middleware_config
    if isinstance(spec, str) and name in config.custom_groups and name not in _seen:
        items: list[_Item] = []
        for sub in config.custom_groups[name]:
            items.extend(_expand(application, sub, _seen | {name}))
        return items
    if isinstance(spec, str) and name in config.aliases:
        return [_Item(key=name, target=config.aliases[name], params=params)]
    if isinstance(spec, str):
        raise RuntimeError(
            f"Middleware alias [{name}] is not defined. Register it with "
            f'`middleware.alias({{"{name}": "pkg.mod:Class"}})` in bootstrap/app.py.'
        )
    return [_Item(key=name, target=spec, params=params)]


def _sort(items: list[_Item], priority: list[str]) -> list[_Item]:
    """Laravel-style priority sort (T-11): named-priority middleware form one sorted block at
    the position of the first priority item; everything else keeps its relative order."""
    if not priority:
        return items
    first = next((i for i, it in enumerate(items) if it.key in priority), None)
    if first is None:
        return items
    before, rest = items[:first], items[first:]
    in_priority = sorted((it for it in rest if it.key in priority), key=lambda it: priority.index(it.key))
    others = [it for it in rest if it.key not in priority]
    return [*before, *in_priority, *others]


def _effective_middleware(d: RouteDefinition) -> list[Any]:
    """The route's own middleware, plus controller-declared middleware filtered by only/except_."""
    specs = list(d.middleware_list)
    controller_cls, action_name = d.controller_action()
    if controller_cls is not None:
        declared = getattr(controller_cls, "middleware", None)
        if callable(declared):
            for entry in declared() or []:
                from aso.http.controller import ControllerMiddleware

                if isinstance(entry, ControllerMiddleware):
                    if entry.only is not None and action_name not in entry.only:
                        continue
                    if entry.except_ is not None and action_name in entry.except_:
                        continue
                    specs.append(entry.middleware)
                else:
                    specs.append(entry)
    return specs


def resolve_items(application: Application, d: RouteDefinition) -> list[_Item]:
    specs = _effective_middleware(d)
    items: list[_Item] = []
    for spec in specs:
        items.extend(_expand(application, spec))
    excluded = {_parse_spec(spec)[0] for spec in d.excluded_middleware}
    items = [it for it in items if it.key not in excluded]
    items.append(_Item(key="bindings", target=d, params=()))
    return _sort(items, application.middleware_config.priority_list)


def _build_layer(item: _Item, app: ASGIApp) -> ASGIApp:
    if item.key == "bindings":
        return BindingsStep(app, item.target)
    from aso.foundation.stack import instantiate

    try:
        return instantiate(item.target, app, *item.params)
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(f"Middleware [{item.key}] could not be resolved ({item.target!r}): {exc}") from exc


def build_route_pipeline(application: Application, d: RouteDefinition, inner: ASGIApp) -> ASGIApp:
    """Wrap `inner` (the route's endpoint ASGI app) with its resolved, sorted middleware."""
    from aso.foundation.stack import Boundary

    def handler() -> Any:
        return application.exception_handler

    def reraise() -> bool:
        return application.raise_exceptions

    items = resolve_items(application, d)
    app: ASGIApp = Boundary(inner, handler, reraise=reraise)
    for item in reversed(items):
        layer = _build_layer(item, app)
        if item.key != "bindings":
            layer = _SkippableInTests(layer, app, item.key)
        app = Boundary(layer, handler, reraise=reraise)
    return app


class _SkippableInTests:
    """Lets `client.without_middleware("auth")` skip a route middleware (T-56).

    The test client puts the aliases (or `"__all__"`) in `scope["state"]["aso.without_middleware"]`.
    The flag is honoured only while `APP_ENV=testing`, so a forged request can never bypass `auth`.
    """

    def __init__(self, layer: ASGIApp, inner: ASGIApp, key: str) -> None:
        self.layer = layer
        self.inner = inner
        self.key = key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        skip = (scope.get("state") or {}).get("aso.without_middleware")
        if skip and (self.key in skip or "__all__" in skip):
            from aso.config import config

            if config("app.environment") == "testing":
                await self.inner(scope, receive, send)
                return
        await self.layer(scope, receive, send)


class BindingsStep:
    """Built-in route-model binding step (T-10): loads bound models into `context.route_params`."""

    def __init__(self, app: ASGIApp, definition: RouteDefinition) -> None:
        self.app = app
        self.definition = definition

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ctx = context.current()
        if ctx is not None:
            ctx.route = self.definition
            path_params = scope.get("path_params", {}) or {}
            for key, value in path_params.items():
                ctx.route_params.setdefault(key, value)
            bound: dict[str, Any] = {}
            for name, model_cls, field in self.definition.model_bindings:
                raw = path_params.get(name)
                if raw is None:
                    continue
                model = await _load_binding(model_cls, field, raw, bound)
                ctx.route_params[name] = model
                bound[name] = model
        await self.app(scope, receive, send)


async def _load_binding(model_cls: Any, field: str | None, raw: Any, bound_so_far: dict[str, Any]) -> Any:
    """Load one route-bound model, scoped through any already-bound parent (T-10: "the child is
    loaded through the parent"). This applies whether the route binds by the primary key (the
    common, `field is None` case -- plain `{comment}`) or by another column (`{post:slug}`): the
    scoping must not depend on which lookup column was used, only on whether a parent precedes
    it in the path. Goes through the model's own query builder (not a raw `select()`), so default
    scopes such as soft-deletes still apply, matching `find_or_fail`/`where(...).first_or_fail()`.
    """
    from aso.database.builder import _pk_column
    from aso.exceptions.types import ModelNotFound

    column = getattr(model_cls, field) if field is not None else _pk_column(model_cls)
    builder = model_cls.where(column == raw)
    for parent in bound_so_far.values():
        fk_name = f"{type(parent).__name__.lower()}_id"
        fk_column = getattr(model_cls, fk_name, None)
        if fk_column is not None:
            builder = builder.where(fk_column == parent.id)
    result = await builder.first()
    if result is None:
        raise ModelNotFound(model_cls.__name__, [raw])
    return result
