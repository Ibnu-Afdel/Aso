"""`inertia()` and the lazy `InertiaResponse`: the full T-16 prop evaluation model.

`inertia()` returns an `InertiaResponse`. It is lazy: nothing is evaluated until Starlette sends
it, so shared props (T-17), flash data (T-18) and history flags set *after* the call still make
it into the page. At send time `build()` runs the protocol's "Prop Evaluation Model":

1. Collect shared props (middleware `share()` + `share_once()` wrapped in `once()`), request-scoped
   `share()` calls, then page props on top. Add `errors` as an always prop.
2. Decide which props are "selected" (dot-path partial reload headers).
3. Resolve each category per the T-16 table, one after another with plain `await`.
4. Build metadata (`mergeProps`, `deferredProps`, `onceProps`, ...).
5. Send JSON (Inertia request) or the root HTML document (first visit).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from markupsafe import Markup
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import Receive, Scope, Send

from aso import context
from aso.exceptions.types import PageNotFound
from aso.inertia.history import consume_clear_history
from aso.inertia.json_encode import to_jsonable
from aso.inertia.property import PropertyContext
from aso.inertia.props import Prop, always

_MISSING = object()

PAGE_EXTENSIONS = (".tsx", ".jsx", ".ts", ".js")


class InertiaResponse(Response):
    def __init__(self, component: str, props: dict[str, Any] | None = None, status_code: int = 200) -> None:
        super().__init__(status_code=status_code)
        self.component = component
        self.props: dict[str, Any] = dict(props or {})
        self.view_data: dict[str, Any] = {}
        self.extra_flash: dict[str, Any] = {}
        self._encrypt_history = False

    # -- fluent builders (T-16) --------------------------------------------------------------

    def with_view_data(self, data: dict[str, Any] | None = None, **kwargs: Any) -> InertiaResponse:
        if data:
            self.view_data.update(data)
        self.view_data.update(kwargs)
        return self

    def with_flash(self, key: str | dict[str, Any], value: Any = None) -> InertiaResponse:
        items = key if isinstance(key, dict) else {key: value}
        self.extra_flash.update(items)
        return self

    def encrypt_history(self) -> InertiaResponse:
        self._encrypt_history = True
        return self

    # -- ASGI ---------------------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = await self.build(scope)
        # Headers set on this lazy response (Retry-After, cookies, `respond()` callbacks) must
        # survive into the response that is actually sent.
        skip = {b"content-length", b"content-type"}
        existing = {k for k, _ in response.raw_headers}
        for key, value in self.raw_headers:
            if key not in skip and (key == b"set-cookie" or key not in existing):
                response.raw_headers.append((key, value))
        await response(scope, receive, send)

    async def build(self, scope: Scope) -> Response:  # noqa: PLR0914 - the prop evaluation model has many parts
        ctx = context.require()
        request = ctx.request
        middleware = ctx.inertia
        headers = request.headers

        _ensure_page_exists(self.component)

        is_inertia = headers.get("x-inertia") == "true"
        prefetch = headers.get("purpose") == "prefetch"
        partial = is_inertia and headers.get("x-inertia-partial-component") == self.component
        only_paths = _split_dot_paths(headers.get("x-inertia-partial-data"))
        except_paths = _split_dot_paths(headers.get("x-inertia-partial-except"))
        except_once = _split_flat(headers.get("x-inertia-except-once-props"))
        reset_keys = _split_flat(headers.get("x-inertia-reset"))
        scroll_intent = headers.get("x-inertia-infinite-scroll-merge-intent")
        error_bag_header = headers.get("x-inertia-error-bag")

        # `.with_flash()` participates in the usual flash hand-off below.
        if self.extra_flash and ctx.session is not None:
            for key, value in self.extra_flash.items():
                ctx.session.flash(key, value)

        shared_mw = await middleware.share(request) if middleware is not None else {}
        shared_once_raw = await middleware.share_once(request) if middleware is not None else {}
        shared_once = {k: (v if isinstance(v, Prop) else Prop(v).once()) for k, v in shared_once_raw.items()}
        shared_top_level = {_top_level(k) for k in (*shared_mw, *shared_once, *ctx.shared)}

        all_props: dict[str, Any] = {**shared_mw, **shared_once, **ctx.shared, **self.props}
        all_props["errors"] = always(lambda: _errors_object(ctx, error_bag_header))

        page_props: dict[str, Any] = {}
        merge_keys: list[str] = []
        deep_merge_keys: list[str] = []
        prepend_keys: list[str] = []
        match_on_paths: list[str] = []
        scroll_keys: list[str] = []
        deferred: dict[str, list[str]] = {}
        rescued: list[str] = []
        once_meta: dict[str, Any] = {}

        for raw_key, raw_value in all_props.items():  # one after another: the request has one AsyncSession
            path = tuple(raw_key.split("."))
            key = raw_key
            prop = raw_value if isinstance(raw_value, Prop) else Prop(raw_value)
            selected = _is_selected(path, only_paths, except_paths)
            resolved: Any = _MISSING

            if prop.always_flag:
                resolved = await _resolve(prop.callback, key, all_props, request)

            elif prop.defer_group is not None:
                if not partial:
                    deferred.setdefault(prop.defer_group, []).append(key)
                elif selected:
                    try:
                        resolved = await _resolve(prop.callback, key, all_props, request)
                    except Exception as exc:  # noqa: BLE001 - rescued per-prop, not a bug
                        if not prop.rescue:
                            raise
                        rescued.append(key)
                        from aso.exceptions import report

                        report(exc)

            elif prop.optional_flag:
                if partial and selected:
                    resolved = await _resolve(prop.callback, key, all_props, request)

            elif prop.once_flag:
                identity = prop.once_as or key
                if not partial:
                    once_meta[identity] = {"prop": key, "expiresAt": _once_expires_at(prop)}
                    skip = key in except_once and not prop.once_fresh
                    if not skip:
                        resolved = await _resolve(prop.callback, key, all_props, request)
                elif selected:
                    resolved = await _resolve(prop.callback, key, all_props, request)

            else:
                if not partial or selected:
                    resolved = await _resolve(prop.callback, key, all_props, request)

            if resolved is _MISSING:
                continue

            _assign(page_props, path, to_jsonable(resolved))

            if key in reset_keys:
                continue
            if prop.scroll_flag:
                scroll_keys.append(key)
            if prop.deep_merge_flag:
                deep_merge_keys.append(key)
            elif prop.merge_flag:
                merge_keys.append(key)
            prepend = prop.prepend_flag or (prop.scroll_flag and scroll_intent == "prepend")
            if prepend and (prop.merge_flag or prop.deep_merge_flag):
                prepend_keys.append(key)
            if prop.match_on_path:
                match_on_paths.append(f"{key}.{prop.match_on_path}")

        url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        version = await middleware.version(request) if middleware is not None else ""

        page: dict[str, Any] = {"component": self.component, "props": page_props, "url": url, "version": version}
        if merge_keys:
            page["mergeProps"] = merge_keys
        if deep_merge_keys:
            page["deepMergeProps"] = deep_merge_keys
        if prepend_keys:
            page["prependProps"] = prepend_keys
        if match_on_paths:
            page["matchPropsOn"] = match_on_paths
        if scroll_keys:
            page["scrollProps"] = scroll_keys
        if deferred and not partial:
            page["deferredProps"] = deferred
        if rescued:
            page["rescuedProps"] = rescued
        if once_meta and not partial:
            page["onceProps"] = once_meta
        if shared_top_level:
            page["sharedProps"] = sorted(shared_top_level)

        from aso.config import config

        if self._encrypt_history or bool(config("inertia.encrypt_history", False)):
            page["encryptHistory"] = True
        if consume_clear_history():
            page["clearHistory"] = True

        if ctx.session is not None and not prefetch:
            flash = _collect_flash(ctx.session)
            if flash:
                page["flash"] = to_jsonable(flash)

        if is_inertia:
            return JSONResponse(page, status_code=self.status_code, headers={"X-Inertia": "true", "Vary": "X-Inertia"})
        html = await self.render_root(page, middleware, request)
        return HTMLResponse(html, status_code=self.status_code, headers={"Vary": "X-Inertia"})

    async def render_root(self, page: dict[str, Any], middleware: Any, request: Any) -> str:
        from aso.inertia.root import render_root_view

        view = await middleware.root_view_for(request) if middleware is not None else "app.html"
        return render_root_view(view, page, self.view_data)


def inertia(component: str, props: dict[str, Any] | None = None) -> InertiaResponse:
    return InertiaResponse(component, props)


class LocationResponse(Response):
    """`location(url)` (T-16): an external redirect Inertia must follow with a full page visit."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ctx = context.current()
        request = ctx.request if ctx is not None else None
        is_inertia = request is not None and request.headers.get("x-inertia") == "true"
        if is_inertia:
            response: Response = Response(status_code=409, headers={"X-Inertia-Location": self.url})
        else:
            from starlette.responses import RedirectResponse

            response = RedirectResponse(self.url, status_code=302)
        await response(scope, receive, send)


def location(url: str) -> LocationResponse:
    return LocationResponse(url)


# -- prop evaluation helpers --------------------------------------------------------------------


async def _resolve(value: Any, key: str, all_props: dict[str, Any], request: Any) -> Any:
    if callable(value):
        value = value()
    if inspect.isawaitable(value):
        value = await value
    to_inertia_property = getattr(value, "to_inertia_property", None)
    if callable(to_inertia_property):
        result = to_inertia_property(PropertyContext(key=key, props=all_props, request=request))
        if inspect.isawaitable(result):
            result = await result
        value = result
    return value


def _top_level(key: str) -> str:
    return key.split(".", 1)[0]


def _assign(tree: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = tree
    for part in path[:-1]:
        node = node.setdefault(part, {})
    node[path[-1]] = value


def _split_dot_paths(raw: str | None) -> list[tuple[str, ...]]:
    if not raw:
        return []
    return [tuple(p.split(".")) for p in raw.split(",") if p]


def _split_flat(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {p for p in raw.split(",") if p}


def _path_overlaps(leaf: tuple[str, ...], requested: tuple[str, ...]) -> bool:
    n = min(len(leaf), len(requested))
    return leaf[:n] == requested[:n]


def _is_selected(path: tuple[str, ...], only_paths: list[tuple[str, ...]], except_paths: list[tuple[str, ...]]) -> bool:
    if only_paths and not any(_path_overlaps(path, o) for o in only_paths):
        return False
    return not any(_path_overlaps(path, e) for e in except_paths)


def _once_expires_at(prop: Prop) -> int | None:
    from datetime import UTC, date, datetime, timedelta

    until = prop.once_until
    if until is None:
        return None
    if isinstance(until, timedelta):
        when = datetime.now(UTC) + until
    elif isinstance(until, datetime):
        when = until
    elif isinstance(until, date):
        when = datetime(until.year, until.month, until.day, tzinfo=UTC)
    else:
        return None
    return int(when.timestamp() * 1000)


def _errors_object(ctx: Any, error_bag_header: str | None) -> dict[str, Any]:
    """T-19 "Errors in the page object": first message per field, scoped to the error bag."""
    from aso.config import config

    session = ctx.session
    bags = session.get("errors") if session is not None else None
    bags = bags if isinstance(bags, dict) else {}
    if not bags:
        return {}
    all_errors = bool(config("inertia.all_errors", False))

    def reduce_bag(bag: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for field, messages in bag.items():
            values = messages if isinstance(messages, list) else [messages]
            out[field] = list(values) if all_errors else (values[0] if values else "")
        return out

    default_bag = bags.get("default")
    if default_bag:
        reduced = reduce_bag(default_bag)
        if error_bag_header:
            return {error_bag_header: reduced}
        return reduced
    return {bag: reduce_bag(fields) for bag, fields in bags.items()}


def _collect_flash(session: Any) -> dict[str, Any]:
    """T-18 "How flash reaches React": visible user flash keys, excluding `_`-prefixed and `errors`.

    Keys delivered with this render are moved from `_flash.new` to `_flash.old` so the next
    request does not show them again (Laravel's `Inertia::flash()` semantics).
    """
    flash_state = session.get("_flash") or {"old": [], "new": []}
    visible = [k for k in (*flash_state["old"], *flash_state["new"]) if not k.startswith("_") and k != "errors"]
    flash = {k: session.get(k) for k in visible}
    for key in list(flash_state["new"]):
        if key in visible:
            flash_state["new"].remove(key)
            flash_state["old"].append(key)
    return flash


def _ensure_page_exists(component: str) -> None:
    """`PageNotFound` when the page file is missing, checked only in `local`/`testing` (T-16)."""
    from aso.foundation.application import current_application

    app = current_application()
    if app is None or not app.environment("local", "testing"):
        return
    from aso.foundation.paths import resource_path

    base = resource_path("js", "pages", *component.split("/"))
    for ext in PAGE_EXTENSIONS:
        if Path(f"{base}{ext}").exists():
            return
    raise PageNotFound(component, f"{base}{PAGE_EXTENSIONS[0]}")


# -- root document rendering ----------------------------------------------------------------


def page_json(page: dict[str, Any]) -> str:
    """Protocol: no HTML escaping inside the script element, but every `/` written as `\\/`."""
    return json.dumps(page, separators=(",", ":")).replace("/", "\\/")


def inertia_app(page: dict[str, Any]) -> Markup:
    return Markup(f'<script data-page="app" type="application/json">{page_json(page)}</script><div id="app"></div>')
