"""Prop modifiers for `inertia()` (T-16): optional, always, defer, merge, deep_merge, once, scroll.

Each factory function wraps a value (usually a callable) in a `Prop`, which records which
Inertia v3 "category" it belongs to and which merge/once modifiers were chained onto it.
Modifier methods mutate and return `self`, so calls like `defer(...).once()`,
`merge(items).append("data", match_on="id")` and `once(...).until(timedelta(days=1))` chain
naturally, matching the Laravel-side fluent API.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


class Prop:
    """A wrapped prop value plus its category/modifier flags.

    Do not construct directly in application code; use the module functions below.
    """

    __slots__ = (
        "callback",
        "optional_flag",
        "always_flag",
        "defer_group",
        "rescue",
        "merge_flag",
        "deep_merge_flag",
        "prepend_flag",
        "match_on_path",
        "once_flag",
        "once_until",
        "once_as",
        "once_fresh",
        "scroll_flag",
    )

    def __init__(self, callback: Any) -> None:
        self.callback = callback
        self.optional_flag = False
        self.always_flag = False
        self.defer_group: str | None = None
        self.rescue = False
        self.merge_flag = False
        self.deep_merge_flag = False
        self.prepend_flag = False
        self.match_on_path: str | None = None
        self.once_flag = False
        self.once_until: timedelta | date | datetime | None = None
        self.once_as: str | None = None
        self.once_fresh = False
        self.scroll_flag = False

    # -- modifiers (chainable) -------------------------------------------------------------

    def append(self, path: str | None = None, match_on: str | None = None) -> Prop:
        self.merge_flag = True
        if match_on is not None:
            self.match_on_path = f"{path}.{match_on}" if path else match_on
        return self

    def prepend(self, path: str | None = None, match_on: str | None = None) -> Prop:
        self.append(path, match_on)
        self.prepend_flag = True
        return self

    def match_on(self, path: str) -> Prop:
        self.match_on_path = path
        return self

    def merge(self) -> Prop:
        self.merge_flag = True
        return self

    def deep_merge(self) -> Prop:
        self.merge_flag = True
        self.deep_merge_flag = True
        return self

    def once(self) -> Prop:
        self.once_flag = True
        return self

    def until(self, value: timedelta | date | datetime) -> Prop:
        self.once_until = value
        return self

    def as_(self, name: str) -> Prop:
        self.once_as = name
        return self

    def fresh(self, is_fresh: bool) -> Prop:
        self.once_fresh = bool(is_fresh)
        return self

    def scroll(self) -> Prop:
        self.scroll_flag = True
        self.merge_flag = True
        return self


# -- factory functions ----------------------------------------------------------------------


def optional(callback: Any) -> Prop:
    """Never sent on a full visit; resolved only when a partial reload asks for it by name."""
    prop = Prop(callback)
    prop.optional_flag = True
    return prop


def always(callback: Any) -> Prop:
    """Sent on every response, even when a partial reload did not select it."""
    prop = Prop(callback)
    prop.always_flag = True
    return prop


def defer(callback: Any, group: str = "default", rescue: bool = False) -> Prop:
    """Left out of the first response; fetched by the client in a follow-up partial reload.

    Props sharing a `group` are fetched together. With `rescue=True`, an exception while
    resolving does not fail the request: the prop is omitted and its key is listed in
    `rescuedProps`.
    """
    prop = Prop(callback)
    prop.defer_group = group
    prop.rescue = rescue
    return prop


def merge(callback: Any) -> Prop:
    """A partial reload appends to this prop instead of replacing it."""
    return Prop(callback).merge()


def deep_merge(callback: Any) -> Prop:
    """Like `merge()`, but merges nested structures recursively instead of only the root."""
    return Prop(callback).deep_merge()


def once(callback: Any) -> Prop:
    """Resolved once, remembered by the client, and not sent again for the same identity."""
    return Prop(callback).once()


def scroll(callback: Any) -> Prop:
    """A merge prop shaped for infinite scrolling (T-34 paginators)."""
    return Prop(callback).scroll()
