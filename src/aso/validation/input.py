"""Step 1 (collect) and step 2 (clean up) of `FormRequest.resolve()` (T-19).

Kept separate from `form_request.py` so the (de)serialisation plumbing — bracket-key expansion,
multipart file handling, trim/empty-to-None — can be unit-tested without booting a request.
"""

from __future__ import annotations

import re
from typing import Any

from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.requests import Request as StarletteRequest

from aso.validation.uploaded_file import UploadedFile

DONT_TRIM = {"password", "password_confirmation", "current_password"}

_BRACKET = re.compile(r"\[([^\]]*)\]")


def clean_input(value: Any, key: str | None = None) -> Any:
    """Step 2: trim strings (except the three password keys), then `"" -> None`, recursively."""
    if isinstance(value, str):
        if key not in DONT_TRIM:
            value = value.strip()
        return value if value != "" else None
    if isinstance(value, dict):
        return {k: clean_input(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_input(v) for v in value]
    return value


def _bracket_path(key: str) -> list[str]:
    """`"lines[0][quantity]"` -> `["lines", "0", "quantity"]`; `"tags[]"` -> `["tags", ""]`."""
    if "[" not in key:
        return [key]
    head, _, rest = key.partition("[")
    return [head, *_BRACKET.findall("[" + rest)]


def _assign(node: dict[str, Any], path: list[str], value: Any) -> None:
    key = path[0] or str(len(node))
    if len(path) == 1:
        node[key] = value
        return
    child = node.get(key)
    if not isinstance(child, dict):
        child = {}
        node[key] = child
    _assign(child, path[1:], value)


def _listify(value: Any) -> Any:
    """Turn any dict whose keys are *all* digit strings into a list, recursively (PHP-style)."""
    if isinstance(value, dict):
        converted = {k: _listify(v) for k, v in value.items()}
        if converted and all(k.isdigit() for k in converted):
            return [converted[k] for k in sorted(converted, key=int)]
        return converted
    return value


def expand_brackets(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Expand `FormData`-style bracket keys (Inertia's `<Form>`/`useForm` conversion) into nested
    dicts/lists. Repeated flat keys (`tags[]`, `tags[]`, ...) append in order."""
    root: dict[str, Any] = {}
    for raw_key, value in pairs:
        _assign(root, _bracket_path(raw_key), value)
    return _listify(root)


async def collect_input(request: StarletteRequest) -> dict[str, Any]:
    """Step 1: query params for `GET`/`HEAD`; query merged with the body otherwise.

    JSON bodies (Inertia's default for non-file submissions) are already nested and are merged
    as-is. Form/multipart bodies go through `expand_brackets`; uploaded files become
    `UploadedFile`. The body is read through the request's own cache (T-11), so this never
    consumes it for anyone downstream.
    """
    data: dict[str, Any] = expand_brackets(list(request.query_params.multi_items()))
    if request.method in ("GET", "HEAD"):
        return data
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        body = await request.json() if await request.body() else {}
        if isinstance(body, dict):
            data.update(body)
    elif "multipart" in content_type or "form" in content_type:
        form = await request.form()
        pairs: list[tuple[str, Any]] = []
        for key, value in form.multi_items():
            if isinstance(value, StarletteUploadFile):
                raw = await value.read()
                await value.seek(0)
                value = UploadedFile.from_upload_file(value, raw)
            pairs.append((key, value))
        data.update(expand_brackets(pairs))
    return data
