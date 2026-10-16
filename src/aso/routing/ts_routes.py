"""`aso routes:generate` (T-28): turn the compiled route registry into typed TypeScript.

Pure generation logic lives here; `aso.console.commands.routes_generate` is the thin
`Command` wrapper that boots the app (via the normal CLI boot path, which already calls
`create_app()` -- T-28 "How it works") and writes the files this module builds.

Scope (documented gaps, see the build report): `Route.include_router()` (plain FastAPI routers)
and the "several routes point at the same controller method" dict-keyed-by-URI case are not
emitted; every other named/unnamed web+api route is.
"""

from __future__ import annotations

import keyword
from dataclasses import dataclass
from pathlib import Path

from aso.routing import paths
from aso.routing.registry import RouteDefinition, RouteRegistry, classify_action

# JS/TS reserved words that cannot be used as a bare export identifier (T-28: "Names that are
# reserved words in JavaScript ... get a trailing underscore in the export").
_JS_RESERVED = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete",
    "do", "else", "export", "extends", "finally", "for", "function", "if", "import", "in",
    "instanceof", "new", "return", "super", "switch", "this", "throw", "try", "typeof", "var",
    "void", "while", "with", "yield", "let", "static", "enum", "await", "implements",
    "interface", "package", "private", "protected", "public",
}


def _safe_export(name: str) -> str:
    return f"{name}_" if name in _JS_RESERVED or keyword.iskeyword(name) else name


@dataclass
class ParamInfo:
    name: str
    optional: bool
    ts_type: str  # "number" | "string"


@dataclass
class RouteInfo:
    definition: RouteDefinition
    methods: list[str]  # upper-case, e.g. ["GET", "HEAD"]
    template: str  # clean path, e.g. "/posts/{post}" or "/archive/{year?}"
    name: str | None
    group: str
    controller_module: str | None
    controller_class: str | None
    method_name: str | None  # None when the action is not a Controller method
    params: list[ParamInfo]


def _ts_type_for_model_field(model_cls: type, field_name: str | None) -> str:
    """`int` columns -> `"number"`; everything else (`str`, `UUID`, ULID...) -> `"string"`
    (T-28 "How it works": "the key type comes from the bound model's primary key column")."""
    try:
        from sqlalchemy import Integer
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(model_cls)
        column = mapper.columns[field_name] if field_name else mapper.primary_key[0]
        return "number" if isinstance(column.type, Integer) else "string"
    except Exception:  # pragma: no cover - defensive: fall back to the always-safe type
        return "string"


def _ts_type_for_path_param(d: RouteDefinition, spec: paths.ParamSpec) -> str:
    for name, model_cls, field in d.model_bindings:
        if name == spec.name:
            return _ts_type_for_model_field(model_cls, field)

    _controller_cls, method, _method_name = classify_action(d.action)
    try:
        import typing as _typing
        import uuid as _uuid

        hints = _typing.get_type_hints(method)
    except Exception:  # pragma: no cover - annotations we cannot resolve stay strings
        hints = {}
    ann = hints.get(spec.name)
    if ann is int:
        return "number"
    if ann is _uuid.UUID:
        return "string"
    return "string"


def collect_routes(registry: RouteRegistry) -> list[RouteInfo]:
    """Every non-fallback route in `registry`, web and api, named or not."""
    infos: list[RouteInfo] = []
    for d in registry.definitions:
        if d.is_fallback:
            continue
        controller_cls, _method, method_name = classify_action(d.action)
        controller_module = controller_cls.__module__ if controller_cls is not None else None
        controller_class = controller_cls.__qualname__ if controller_cls is not None else None
        template = paths.clean_path(d.path)
        specs = paths.parse_params(d.path)
        params = [
            ParamInfo(name=s.name, optional=s.optional, ts_type=_ts_type_for_path_param(d, s))
            for s in specs
        ]
        infos.append(
            RouteInfo(
                definition=d,
                methods=[m.upper() for m in d.methods],
                template=template,
                name=d.route_name,
                group=d.group,
                controller_module=controller_module,
                controller_class=controller_class,
                method_name=method_name if controller_cls is not None else None,
                params=params,
            )
        )
    return infos


def default_method(methods: list[str]) -> str:
    """The first non-`HEAD` method (T-28: `get` for `GET|HEAD`, `put` for `PUT|PATCH`)."""
    for m in methods:
        if m != "HEAD":
            return m.lower()
    return "get"


def _args_type_name(export_name: str) -> str:
    # "update" -> "UpdateArgs"; safe-exported names keep their trailing underscore.
    base = export_name[:-1] if export_name.endswith("_") else export_name
    return f"{base[:1].upper()}{base[1:]}Args"


def _args_type(params: list[ParamInfo]) -> str | None:
    if not params:
        return None
    if len(params) == 1:
        p = params[0]
        parts = [p.ts_type, f"{{ {p.name}: {p.ts_type} }}"]
        if p.name != "id":
            parts.append(f"{{ id: {p.ts_type} }}")
        parts.append(f"[{p.ts_type}]")
        return " | ".join(parts)
    obj = ", ".join(f"{p.name}: {p.ts_type}" for p in params)
    arr = ", ".join(p.ts_type for p in params)
    return f"{{ {obj} }} | [{arr}]"


def _render_route_function(export_name: str, info: RouteInfo, with_form: bool) -> str:
    """One Wayfinder-shaped export: a callable with `.definition`, `.url`, one method per allowed
    HTTP verb, and (with `--with-form`) `.form` -- all attached in a single `Object.assign` so the
    result's inferred type carries every property (T-28 "Emission")."""
    methods = info.methods
    params = info.params
    template = info.template
    default = default_method(methods)
    names = [p.name for p in params]
    args_type = _args_type(params)
    param_names_literal = "[" + ", ".join(f'"{n}"' for n in names) + "]"

    lines: list[str] = []
    if args_type is not None:
        type_name = _args_type_name(export_name)
        lines.append(f"export type {type_name} = {args_type};")
        lines.append("")
        sig = f"args: {type_name}, options?: RouteQueryOptions"
        call_args = "args, options"
    else:
        sig = "options?: RouteQueryOptions"
        call_args = "options"

    url_fn = f"_{export_name}Url"
    if args_type is None:
        lines.append(f"function {url_fn}(options?: RouteQueryOptions): string {{")
        lines.append(f'    return withQuery("{template}", options);')
        lines.append("}")
    else:
        lines.append(f"function {url_fn}({sig}): string {{")
        lines.append(f"    const params = resolveArgs(args, {param_names_literal});")
        lines.append(f'    return withQuery(buildPath("{template}", params), options);')
        lines.append("}")
    lines.append("")

    methods_literal = "[" + ", ".join(f'"{m.lower()}"' for m in methods) + "] as const"

    lines.append(f"export const {export_name} = Object.assign(")
    lines.append(
        f'    ({sig}): RouteDefinition<"{default}"> => ({{ url: {url_fn}({call_args}), method: "{default}" }}),'
    )
    lines.append("    {")
    lines.append(f'        definition: {{ methods: {methods_literal}, url: "{template}" }},')
    lines.append(f"        url: {url_fn},")
    for m in methods:
        lower = m.lower()
        lines.append(
            f'        {lower}: ({sig}): RouteDefinition<"{lower}"> => '
            f'({{ url: {url_fn}({call_args}), method: "{lower}" }}),'
        )
    if with_form:
        lines.append(
            f"        form: ({sig}): FormDefinition => formFor({url_fn}({call_args}), \"{default}\"),"
        )
    lines.append("    },")
    lines.append(");")
    return "\n".join(lines)


_GENERATED_BANNER = (
    "// GENERATED by `aso routes:generate` (T-28). Do not edit -- this file is rewritten\n"
    "// from scratch on every run and is listed in .gitignore.\n"
)


def _module_header() -> str:
    return (
        _GENERATED_BANNER
        + 'import { buildPath, formFor, resolveArgs, withQuery } from "@/wayfinder";\n'
        + 'import type { FormDefinition, RouteDefinition, RouteQueryOptions } from "@/wayfinder";\n'
    )


def _name_parts(name: str) -> tuple[list[str], str]:
    parts = name.split(".")
    return parts[:-1], _safe_export(parts[-1])


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        return False
    path.write_text(content)
    return True


def _prune_stale(root: Path, keep: set[Path]) -> None:
    """Delete every `*.ts` file under `root` that is not in `keep` (and the directories that
    fall empty as a result), without touching files we are about to rewrite anyway -- so
    `_write_if_changed` can still see their previous content (T-28 "Determinism")."""
    if not root.exists():
        return
    for old in sorted(root.rglob("*.ts"), reverse=True):
        if old not in keep:
            old.unlink()
    for leftover in sorted(root.rglob("*"), reverse=True):
        if leftover.is_dir() and not any(leftover.iterdir()):
            leftover.rmdir()


def generate(
    base_path: Path,
    registry: RouteRegistry,
    *,
    skip_routes: bool = False,
    skip_actions: bool = False,
    with_form: bool = False,
) -> dict[str, bool]:
    """Write `resources/js/routes/**`, `resources/js/actions/**` and `resources/js/wayfinder/`
    under `base_path`. Returns `{relative_path: changed}` for every file considered, sorted
    output, rewritten only when its content actually changes (T-28 "Determinism")."""
    infos = collect_routes(registry)
    js_dir = base_path / "resources" / "js"
    written: dict[str, bool] = {}

    runtime_path = js_dir / "wayfinder" / "index.ts"
    written[str(runtime_path.relative_to(base_path))] = _write_if_changed(runtime_path, _RUNTIME_SOURCE)

    if not skip_routes:
        named = [i for i in infos if i.name]
        by_module: dict[tuple[str, ...], list[tuple[str, RouteInfo]]] = {}
        for info in named:
            assert info.name is not None
            folder_parts, export_name = _name_parts(info.name)
            by_module.setdefault(tuple(folder_parts), []).append((export_name, info))

        routes_root = js_dir / "routes"
        route_files: dict[Path, str] = {}
        for folder_parts, exports in sorted(by_module.items()):
            exports.sort(key=lambda pair: pair[0])
            rel = Path(*folder_parts, "index.ts") if folder_parts else Path("index.ts")
            path = routes_root / rel
            blocks = [_module_header()]
            blocks.extend(_render_route_function(name, info, with_form) for name, info in exports)
            route_files[path] = "\n\n".join(blocks) + "\n"

        _prune_stale(routes_root, set(route_files))
        for path, content in route_files.items():
            written[str(path.relative_to(base_path))] = _write_if_changed(path, content)

    if not skip_actions:
        by_controller: dict[str, list[tuple[str, RouteInfo]]] = {}
        for info in infos:
            if info.controller_module is None or info.method_name is None:
                continue
            by_controller.setdefault(info.controller_module, []).append((info.method_name, info))

        actions_root = js_dir / "actions"
        action_files: dict[Path, str] = {}
        for module, pairs in sorted(by_controller.items()):
            pairs.sort(key=lambda pair: pair[0])
            path = (actions_root / Path(*module.split("."))).with_suffix(".ts")
            blocks = [_module_header()]
            default_entries: list[str] = []
            seen: set[str] = set()
            for method_name, info in pairs:
                if method_name in seen:
                    # Two routes resolving to the same controller method: Wayfinder keys the
                    # export by URI/verb in this case. Not implemented (documented gap); the
                    # first route reaching this method wins.
                    continue
                seen.add(method_name)
                if method_name == "__call__":
                    class_name = (info.controller_class or "Action").split(".")[-1]
                    blocks.append(_render_route_function("_default", info, with_form))
                    blocks.append(f"export default _default;  // {class_name} (single-action controller)")
                else:
                    export_name = _safe_export(method_name)
                    blocks.append(_render_route_function(export_name, info, with_form))
                    default_entries.append(f"    {method_name}: {export_name},")
            if default_entries:
                blocks.append("export default {\n" + "\n".join(default_entries) + "\n};")
            action_files[path] = "\n\n".join(blocks) + "\n"

        _prune_stale(actions_root, set(action_files))
        for path, content in action_files.items():
            written[str(path.relative_to(base_path))] = _write_if_changed(path, content)

    return written


_RUNTIME_SOURCE = '''// GENERATED by `aso routes:generate` (T-28). Do not edit -- this file is rewritten from
// scratch on every run and is listed in .gitignore. Small shared runtime used by every generated
// module under `resources/js/routes/` and `resources/js/actions/`.

export type RouteDefinition<M extends string = string> = {
    url: string;
    method: M;
};

export type FormDefinition = {
    action: string;
    method: "get" | "post";
};

export type RouteQueryOptions = {
    query?: Record<string, unknown>;
    mergeQuery?: Record<string, unknown>;
};

export function encodeParam(value: unknown): string {
    return encodeURIComponent(String(value));
}

/** `args` may be a bare scalar, `{ <name>: value }`, `{ id: value }`, any object carrying one of
 * those keys (e.g. a model instance), or a positional array -- see T-28 "Arguments". */
export function resolveArgs(
    args: unknown,
    names: string[],
): Record<string, string | number | undefined> {
    if (args === undefined || args === null) {
        return {};
    }
    if (Array.isArray(args)) {
        const result: Record<string, string | number | undefined> = {};
        names.forEach((name, index) => {
            result[name] = args[index] as string | number | undefined;
        });
        return result;
    }
    if (typeof args === "string" || typeof args === "number") {
        return { [names[0]]: args };
    }
    if (typeof args === "object") {
        const obj = args as Record<string, unknown>;
        const result: Record<string, string | number | undefined> = {};
        for (const name of names) {
            if (name in obj) {
                result[name] = obj[name] as string | number;
            } else if ("id" in obj) {
                result[name] = obj.id as string | number;
            }
        }
        return result;
    }
    return {};
}

/** Fills a path template (`"/posts/{post}"`, `"/archive/{year?}"`) in; a missing
 * optional segment is dropped, matching `aso.routing.paths.build_url`. */
export function buildPath(
    template: string,
    params: Record<string, string | number | undefined>,
): string {
    const segments = template
        .split("/")
        .filter((segment) => segment.length > 0)
        .map((segment) => {
            const match = /^\\{(\\w+)(\\?)?\\}$/.exec(segment);
            if (!match) {
                return segment;
            }
            const value = params[match[1]];
            if (value === undefined) {
                if (match[2]) {
                    return null;
                }
                throw new Error(`Missing [${match[1]}] parameter for route [${template}].`);
            }
            return encodeParam(value);
        })
        .filter((segment): segment is string => segment !== null);
    return segments.length > 0 ? `/${segments.join("/")}` : "/";
}

function flattenQuery(key: string, value: unknown): string[] {
    if (value === null || value === undefined) {
        return [];
    }
    if (Array.isArray(value)) {
        return value.flatMap((item) => flattenQuery(`${key}[]`, item));
    }
    if (typeof value === "object") {
        return Object.entries(value as Record<string, unknown>).flatMap(([childKey, childValue]) =>
            flattenQuery(`${key}[${childKey}]`, childValue),
        );
    }
    return [`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`];
}

function buildQueryString(params: Record<string, unknown>): string {
    const pairs = Object.entries(params).flatMap(([key, value]) => flattenQuery(key, value));
    return pairs.length > 0 ? `?${pairs.join("&")}` : "";
}

function currentQuery(): Record<string, unknown> {
    if (typeof window === "undefined") {
        return {};
    }
    const result: Record<string, unknown> = {};
    for (const [key, value] of new URLSearchParams(window.location.search).entries()) {
        result[key] = value;
    }
    return result;
}

function mergedQuery(overrides: Record<string, unknown>): Record<string, unknown> {
    const result = currentQuery();
    for (const [key, value] of Object.entries(overrides)) {
        if (value === null) {
            delete result[key];
        } else {
            result[key] = value;
        }
    }
    return result;
}

export function withQuery(url: string, options?: RouteQueryOptions): string {
    if (!options) {
        return url;
    }
    if (options.mergeQuery) {
        return url + buildQueryString(mergedQuery(options.mergeQuery));
    }
    if (options.query) {
        return url + buildQueryString(options.query);
    }
    return url;
}

/** `--with-form`: HTML forms only understand GET/POST, so PUT/PATCH/DELETE spoof via `_method`
 * (T-10), matching the backend's `MethodSpoofing` middleware. */
export function formFor(url: string, method: string): FormDefinition {
    const upper = method.toUpperCase();
    if (upper === "GET" || upper === "POST") {
        return { action: url, method: upper.toLowerCase() as "get" | "post" };
    }
    const separator = url.includes("?") ? "&" : "?";
    return { action: `${url}${separator}_method=${upper}`, method: "post" };
}
'''
