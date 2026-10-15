"""`AssertableInertia`: the fluent page object `TestResponse.assert_inertia()` hands to its
callback (T-56 "Testing Inertia pages").

Strictness: inside a scope (`has(key, fn)`, `each(key, fn)`) every prop of that object must be
either explicitly checked or waved through with `.etc()`. The top-level page is never strict
(T-56 "Strictness").
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["AssertableInertia"]

_MISSING = object()

_JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _dig(data: Any, key: str, default: Any = _MISSING) -> Any:
    node = data
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return node


def _preview(value: Any, limit: int = 400) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _matches_json_type(value: Any, name: str) -> bool:
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    if name == "string":
        return isinstance(value, str)
    return False


class AssertableInertia:
    """Wraps one Inertia page object (or a scope inside it, e.g. the first item of a list prop)."""

    def __init__(
        self,
        page: dict[str, Any],
        *,
        scope: Any = None,
        path: str = "",
        strict: bool = False,
    ) -> None:
        self._page = page
        self._scope = scope if scope is not None else page.get("props", {})
        self._path = path
        self._strict = strict
        self._checked: set[str] = set()
        self._etc_called = False

    # ------------------------------------------------------------ page-level

    def component(self, name: str) -> AssertableInertia:
        actual = self._page.get("component")
        assert actual == name, f"Expected Inertia component [{name}], got [{actual}]."
        return self

    def url(self, path: str) -> AssertableInertia:
        actual = self._page.get("url")
        assert actual == path, f"Expected Inertia url [{path}], got [{actual}]."
        return self

    def version(self, version: str) -> AssertableInertia:
        actual = self._page.get("version")
        assert actual == version, f"Expected Inertia version [{version}], got [{actual}]."
        return self

    # ------------------------------------------------------------ props

    def _label(self, key: str) -> str:
        return f"{self._path}.{key}" if self._path else key

    def has(
        self,
        key: str,
        count: int | Callable[[AssertableInertia], Any] | None = None,
        callback: Callable[[AssertableInertia], Any] | None = None,
    ) -> AssertableInertia:
        if callable(count) and callback is None:
            callback, count = count, None
        value = _dig(self._scope, key)
        assert value is not _MISSING, (
            f"Property [{self._label(key)}] does not exist. Available: {sorted(self._available_keys())}."
        )
        self._checked.add(key.split(".")[0])
        if count is not None:
            assert hasattr(value, "__len__"), f"Property [{self._label(key)}] is not countable: {_preview(value)}."
            assert len(value) == count, (
                f"Property [{self._label(key)}] has {len(value)} item(s), expected {count}: {_preview(value)}."
            )
        if callback is not None:
            target = value[0] if isinstance(value, list) and value else value
            sub = AssertableInertia(self._page, scope=target if isinstance(target, dict) else {}, path=self._label(key), strict=True)
            callback(sub)
            sub._finalize()
        return self

    def each(self, key: str, callback: Callable[[AssertableInertia], Any]) -> AssertableInertia:
        value = _dig(self._scope, key)
        assert isinstance(value, list), f"Property [{self._label(key)}] is not a list: {_preview(value)}."
        self._checked.add(key.split(".")[0])
        for index, item in enumerate(value):
            sub = AssertableInertia(self._page, scope=item, path=f"{self._label(key)}[{index}]", strict=True)
            callback(sub)
            sub._finalize()
        return self

    def has_all(self, *keys: str) -> AssertableInertia:
        for key in keys:
            self.has(key)
        return self

    def missing(self, key: str) -> AssertableInertia:
        value = _dig(self._scope, key)
        assert value is _MISSING, f"Property [{self._label(key)}] is unexpectedly present: {_preview(value)}."
        return self

    def missing_all(self, *keys: str) -> AssertableInertia:
        for key in keys:
            self.missing(key)
        return self

    def where(self, key: str, expected: Any) -> AssertableInertia:
        actual = _dig(self._scope, key)
        assert actual is not _MISSING, f"Property [{self._label(key)}] does not exist."
        self._checked.add(key.split(".")[0])
        if callable(expected):
            assert expected(actual), f"Property [{self._label(key)}] = {_preview(actual)} failed its predicate."
        else:
            assert actual == expected, (
                f"Property [{self._label(key)}] = {_preview(actual)}, expected {_preview(expected)}."
            )
        return self

    def where_type(self, key: str, type_name: str) -> AssertableInertia:
        actual = _dig(self._scope, key)
        assert actual is not _MISSING, f"Property [{self._label(key)}] does not exist."
        self._checked.add(key.split(".")[0])
        names = [t.strip() for t in type_name.split("|")]
        for name in names:
            assert name in _JSON_TYPES, f"Unknown JSON type [{name}] in where_type()."
        ok = any(_matches_json_type(actual, name) for name in names)
        assert ok, f"Property [{self._label(key)}] = {_preview(actual)} is not of type [{type_name}]."
        return self

    def etc(self) -> AssertableInertia:
        self._etc_called = True
        return self

    # ------------------------------------------------------------ flash / metadata

    def has_flash(self, key: str, value: Any = _MISSING) -> AssertableInertia:
        flash = self._page.get("flash") or {}
        assert key in flash, f"Flash key [{key}] is not on the page. Flash: {sorted(flash)}."
        if value is not _MISSING:
            assert flash[key] == value, f"Flash[{key}] = {_preview(flash[key])}, expected {_preview(value)}."
        return self

    def missing_flash(self, key: str) -> AssertableInertia:
        flash = self._page.get("flash") or {}
        assert key not in flash, f"Flash key [{key}] is unexpectedly present: {_preview(flash[key])}."
        return self

    def has_deferred(self, key: str, group: str = "default") -> AssertableInertia:
        deferred = self._page.get("deferredProps") or {}
        group_props = deferred.get(group, [])
        assert key in group_props, (
            f"Property [{key}] is not announced as deferred in group [{group}]. Deferred: {deferred!r}."
        )
        return self

    def has_merge(self, key: str) -> AssertableInertia:
        merge = set(self._page.get("mergeProps") or []) | set(self._page.get("deepMergeProps") or [])
        assert key in merge, f"Property [{key}] is not a merge prop. mergeProps: {sorted(merge)}."
        return self

    def has_once(self, key: str) -> AssertableInertia:
        once_meta = self._page.get("onceProps") or {}
        matches = key in once_meta or any(meta.get("prop") == key for meta in once_meta.values())
        assert matches, f"Property [{key}] is not a once prop. onceProps: {once_meta!r}."
        return self

    def encrypts_history(self) -> AssertableInertia:
        assert self._page.get("encryptHistory") is True, "Expected the page to encrypt history, it does not."
        return self

    # ------------------------------------------------------------ internals

    def _available_keys(self) -> list[str]:
        return list(self._scope.keys()) if isinstance(self._scope, dict) else []

    def _finalize(self) -> None:
        if self._etc_called or not self._strict:
            return
        if not isinstance(self._scope, dict):
            return
        unchecked = set(self._scope.keys()) - self._checked
        assert not unchecked, (
            f"Unexpected/unverified prop(s) {sorted(unchecked)} at [{self._path}]. "
            "Check them explicitly, or call .etc() to allow unchecked props."
        )
