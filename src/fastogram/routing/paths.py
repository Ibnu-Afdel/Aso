"""Route path parsing and compilation helpers (T-10).

Route paths recorded by `Route.get(...)` use Laravel-style tokens: `{name}`, `{name?}`
(optional; must be trailing), and `{name:field}` (route-model binding by column). The colon form
is **never** a Starlette path-convertor type -- those are added by the compiler itself, from
`.where()` or from the controller's `int`/`UUID` annotations, never typed by the route author.

This module assumes (true of every example in T-10) that a path segment is either a literal
string or exactly one `{...}` token -- never mixed, e.g. `/{a}-{b}/`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

_PARAM = re.compile(r"^\{(\w+)(?::(\w+))?(\?)?\}$")


@dataclass
class ParamSpec:
    name: str
    binding_field: str | None = None
    optional: bool = False


def _segments(path: str) -> list[str]:
    stripped = path.strip("/")
    return stripped.split("/") if stripped else []


def parse_params(path: str) -> list[ParamSpec]:
    """Every `{...}` token in `path`, left to right. Raises if an optional param is not trailing."""
    specs: list[ParamSpec] = []
    seen_optional = False
    for seg in _segments(path):
        m = _PARAM.match(seg)
        if not m:
            continue
        spec = ParamSpec(m.group(1), m.group(2), bool(m.group(3)))
        if spec.optional:
            seen_optional = True
        elif seen_optional:
            raise ValueError(f"Optional route parameters must be trailing: {path!r}")
        specs.append(spec)
    return specs


def clean_path(path: str) -> str:
    """`{post:slug}` -> `{post}`, `{year?}` stays `{year?}` (the form kept in the registry)."""
    out = []
    for seg in _segments(path):
        m = _PARAM.match(seg)
        if m:
            out.append("{" + m.group(1) + "}" + ("?" if m.group(3) else ""))
        else:
            out.append(seg)
    return "/" + "/".join(out) if out else "/"


def compiled_variants(path: str, type_for: Callable[[str], str | None]) -> list[str]:
    """One Starlette path per combination of trailing optional params present, fullest first.

    `type_for(name)` returns a Starlette convertor name (`"int"`, `"uuid"`, or a `fg_...` hash
    for a `.where()` pattern) for that parameter, or `None` for the default string convertor.
    """
    segs = _segments(path)
    specs = parse_params(path)
    optional_names = [s.name for s in specs if s.optional]
    variants: list[str] = []
    for drop in range(len(optional_names) + 1):
        excluded = set(optional_names[len(optional_names) - drop :]) if drop else set()
        kept: list[str] = []
        for seg in segs:
            m = _PARAM.match(seg)
            if not m:
                kept.append(seg)
                continue
            name = m.group(1)
            if name in excluded:
                continue
            conv = type_for(name)
            kept.append(f"{{{name}:{conv}}}" if conv else f"{{{name}}}")
        variants.append("/" + "/".join(kept) if kept else "/")
    return variants


def build_url(path: str, values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Substitute `values` into `path`'s tokens; missing optional params drop their segment.

    Returns `(url_path, remaining_values)` -- remaining values become the query string.
    """
    remaining = dict(values)
    out: list[str] = []
    for seg in _segments(path):
        m = _PARAM.match(seg)
        if not m:
            out.append(seg)
            continue
        name, _field, optional = m.group(1), m.group(2), bool(m.group(3))
        if name in remaining:
            out.append(quote(str(remaining.pop(name)), safe=""))
        elif optional:
            continue
        else:
            raise KeyError(f"Missing [{name}] parameter for route [{path}].")
    return ("/" + "/".join(out) if out else "/"), remaining
