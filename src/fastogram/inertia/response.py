"""`inertia()` and the lazy `InertiaResponse` (T-16), proven by spike S-1.

SEED (spine): regular/callable/deferred props, partial reloads (only), errors, flash hand-off,
JSON vs HTML. The inertia package task completes the full T-16 prop evaluation model (optional,
always, merge, deep_merge, once, scroll, rescue, except, dot paths), metadata fields, history
flags, view data, PageNotFound, and the JSON encoder.
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from markupsafe import Markup
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import Receive, Scope, Send

from fastogram import context


class DeferProp:
    def __init__(self, callback: Any, group: str = "default") -> None:
        self.callback = callback
        self.group = group


def defer(callback: Any, group: str = "default") -> DeferProp:
    return DeferProp(callback, group)


async def resolve_value(value: Any) -> Any:
    if callable(value):
        value = value()
    if inspect.isawaitable(value):
        value = await value
    return value


def to_jsonable(value: Any) -> Any:
    from fastapi.encoders import jsonable_encoder

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict) and not isinstance(value, type):
        return to_jsonable(to_dict())
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return jsonable_encoder(value)


class InertiaResponse(Response):
    def __init__(self, component: str, props: dict[str, Any] | None = None, status_code: int = 200) -> None:
        super().__init__(status_code=status_code)
        self.component = component
        self.props = props or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = await self.build(scope)
        await response(scope, receive, send)

    async def build(self, scope: Scope) -> Response:
        ctx = context.require()
        request = ctx.request
        middleware = ctx.inertia
        headers = request.headers
        is_inertia = headers.get("x-inertia") == "true"
        partial = is_inertia and headers.get("x-inertia-partial-component") == self.component
        only = [k for k in (headers.get("x-inertia-partial-data") or "").split(",") if k]

        shared = await middleware.share(request) if middleware is not None else {}
        props = {**shared, **ctx.shared, **self.props}
        page_props: dict[str, Any] = {}
        deferred: dict[str, list[str]] = {}
        for key, value in props.items():  # one after another: the request has one AsyncSession
            if partial and only and key not in only:
                continue
            if isinstance(value, DeferProp):
                if not partial:
                    deferred.setdefault(value.group, []).append(key)
                    continue
                value = value.callback
            page_props[key] = to_jsonable(await resolve_value(value))

        session = ctx.session
        errors = (session.get("errors") or {}) if session is not None else {}
        default_bag = errors.get("default", {}) if isinstance(errors, dict) else {}
        page_props["errors"] = {k: (v[0] if isinstance(v, list) else v) for k, v in default_bag.items()}

        url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        version = await middleware.version(request) if middleware is not None else ""
        page: dict[str, Any] = {"component": self.component, "props": page_props, "url": url, "version": version}
        if deferred:
            page["deferredProps"] = deferred
        if session is not None and headers.get("purpose") != "prefetch":
            flash_state = session.get("_flash") or {"old": [], "new": []}
            visible = [k for k in [*flash_state["old"], *flash_state["new"]] if not k.startswith("_") and k != "errors"]
            flash = {k: session.get(k) for k in visible}
            for key in list(flash_state["new"]):
                if key in visible:
                    flash_state["new"].remove(key)
                    flash_state["old"].append(key)
            if flash:
                page["flash"] = to_jsonable(flash)

        if is_inertia:
            return JSONResponse(page, status_code=self.status_code, headers={"X-Inertia": "true", "Vary": "X-Inertia"})
        html = await self.render_root(page, middleware, request)
        return HTMLResponse(html, status_code=self.status_code, headers={"Vary": "X-Inertia"})

    async def render_root(self, page: dict[str, Any], middleware: Any, request: Any) -> str:
        from fastogram.inertia.root import render_root_view

        view = await middleware.root_view_for(request) if middleware is not None else "app.html"
        return render_root_view(view, page)


def inertia(component: str, props: dict[str, Any] | None = None) -> InertiaResponse:
    return InertiaResponse(component, props)


def page_json(page: dict[str, Any]) -> str:
    """Protocol: no HTML escaping inside the script element, but every `/` written as `\\/`."""
    return json.dumps(page, separators=(",", ":")).replace("/", "\\/")


def inertia_app(page: dict[str, Any]) -> Markup:
    return Markup(f'<script data-page="app" type="application/json">{page_json(page)}</script><div id="app"></div>')
