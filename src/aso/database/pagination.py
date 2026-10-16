"""Paginators (T-34): `LengthAwarePaginator`, `SimplePaginator`, `CursorPaginator`.

`to_dict()` on every paginator matches Laravel 13's `toArray()` keys exactly, because the Inertia
layer (T-16) serialises any prop with a `to_dict()` method by calling it.
"""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from sqlalchemy.sql import operators

if TYPE_CHECKING:
    from aso.database.builder import Builder

__all__ = ["CursorPaginator", "LengthAwarePaginator", "SimplePaginator"]


def _current_request() -> Any:
    from aso.context import current

    ctx = current()
    return ctx.request if ctx is not None else None


def _default_path() -> str:
    from aso.config import config

    base = (config("app.url", "") or "").rstrip("/")
    req = _current_request()
    path = req.url.path if req is not None else ""
    return f"{base}{path}" if base else path


def _current_query_params() -> dict[str, Any]:
    req = _current_request()
    if req is None:
        return {}
    return dict(req.query_params)


def _read_page(page: int | None, page_name: str) -> int:
    if page is not None:
        try:
            value = int(page)
        except (TypeError, ValueError):
            return 1
        return value if value >= 1 else 1
    req = _current_request()
    raw = req.query_params.get(page_name) if req is not None else None
    if raw is None:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value if value >= 1 else 1


def _serialize(item: Any) -> Any:
    to_dict = getattr(item, "to_dict", None)
    return to_dict() if callable(to_dict) else item


class _BasePaginator:
    def __init__(self, items: list[Any], per_page: int, current_page: Any, page_name: str) -> None:
        self.items = items
        self.per_page = per_page
        self.current_page = current_page
        self.page_name = page_name
        self._path: str | None = None
        self._with_query_string = False
        self._appends: dict[str, Any] = {}
        self._fragment: str | None = None
        self._on_each_side = 3

    def with_query_string(self) -> Any:
        self._with_query_string = True
        return self

    def appends(self, params: dict[str, Any]) -> Any:
        self._appends.update(params)
        return self

    def with_path(self, path: str) -> Any:
        self._path = path
        return self

    def fragment(self, value: str) -> Any:
        self._fragment = value
        return self

    def on_each_side(self, n: int) -> Any:
        self._on_each_side = n
        return self

    def through(self, fn: Callable[[Any], Any]) -> Any:
        self.items = [fn(i) for i in self.items]
        return self

    def __iter__(self) -> Any:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Any:
        return self.items[index]

    def _base_path(self) -> str:
        return self._path if self._path is not None else _default_path()

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self._with_query_string:
            params.update(_current_query_params())
        params.update(self._appends)
        return params

    def _url_for(self, value: Any) -> str | None:
        if value is None:
            return None
        params = self._base_params()
        params[self.page_name] = value
        qs = urlencode(params)
        url = self._base_path()
        if qs:
            url = f"{url}?{qs}"
        if self._fragment:
            url = f"{url}#{self._fragment}"
        return url


class LengthAwarePaginator(_BasePaginator):
    total: int
    last_page: int

    @classmethod
    async def create(cls, builder: Builder[Any], per_page: int, page: int | None, page_name: str) -> LengthAwarePaginator:
        resolved_page = _read_page(page, page_name)
        total = await builder.count()
        last_page = max(1, math.ceil(total / per_page)) if total else 1
        resolved_page = min(resolved_page, last_page) if total else resolved_page
        items = await builder.for_page(resolved_page, per_page).get() if total else []
        paginator = cls(items, per_page, resolved_page, page_name)
        paginator.total = total
        paginator.last_page = last_page
        return paginator

    def _page_numbers(self) -> list[int | None]:
        last, current, side = self.last_page, self.current_page, self._on_each_side
        if last < side * 2 + 8:
            return list(range(1, last + 1))
        window = side + 4
        if current <= window:
            return [*range(1, window + 1), None, last - 1, last]
        if current >= last - window + 1:
            return [1, 2, None, *range(last - window + 1, last + 1)]
        return [1, 2, None, *range(current - side, current + side + 1), None, last - 1, last]

    def _links(self) -> list[dict[str, Any]]:
        current, last = self.current_page, self.last_page
        links = [
            {
                "url": self._url_for(current - 1) if current > 1 else None,
                "label": "&laquo; Previous",
                "page": current - 1 if current > 1 else None,
                "active": False,
            }
        ]
        for p in self._page_numbers():
            if p is None:
                links.append({"url": None, "label": "...", "page": None, "active": False})
            else:
                links.append({"url": self._url_for(p), "label": str(p), "page": p, "active": p == current})
        links.append(
            {
                "url": self._url_for(current + 1) if current < last else None,
                "label": "Next &raquo;",
                "page": current + 1 if current < last else None,
                "active": False,
            }
        )
        return links

    def to_dict(self) -> dict[str, Any]:
        current, last = self.current_page, self.last_page
        from_ = (current - 1) * self.per_page + 1 if self.items else None
        to_ = from_ + len(self.items) - 1 if self.items else None
        return {
            "current_page": current,
            "data": [_serialize(i) for i in self.items],
            "first_page_url": self._url_for(1),
            "from": from_,
            "last_page": last,
            "last_page_url": self._url_for(last),
            "links": self._links(),
            "next_page_url": self._url_for(current + 1) if current < last else None,
            "path": self._base_path(),
            "per_page": self.per_page,
            "prev_page_url": self._url_for(current - 1) if current > 1 else None,
            "to": to_,
            "total": self.total,
        }


class SimplePaginator(_BasePaginator):
    _has_more: bool

    @classmethod
    async def create(cls, builder: Builder[Any], per_page: int, page: int | None, page_name: str) -> SimplePaginator:
        resolved_page = _read_page(page, page_name)
        # Not `builder.for_page(resolved_page, per_page + 1)`: `for_page()` derives the OFFSET from
        # its *second* argument too, so passing `per_page + 1` there also inflates the offset
        # (`(page - 1) * (per_page + 1)` instead of `(page - 1) * per_page`), skipping real rows
        # on every page after the first. Only the LIMIT needs the "+1 to detect a next page" trick.
        rows = await builder.limit(per_page + 1).offset((resolved_page - 1) * per_page).get()
        has_more = len(rows) > per_page
        paginator = cls(rows[:per_page], per_page, resolved_page, page_name)
        paginator._has_more = has_more
        return paginator

    def to_dict(self) -> dict[str, Any]:
        current = self.current_page
        from_ = (current - 1) * self.per_page + 1 if self.items else None
        to_ = from_ + len(self.items) - 1 if self.items else None
        return {
            "current_page": current,
            "current_page_url": self._url_for(current),
            "data": [_serialize(i) for i in self.items],
            "first_page_url": self._url_for(1),
            "from": from_,
            "next_page_url": self._url_for(current + 1) if self._has_more else None,
            "path": self._base_path(),
            "per_page": self.per_page,
            "prev_page_url": self._url_for(current - 1) if current > 1 else None,
            "to": to_,
        }


def _order_spec(builder: Builder[Any]) -> list[tuple[Any, bool]]:
    if not builder._order:
        raise ValueError("cursor_paginate() needs an order_by() on unique column(s).")
    specs = []
    for expr in builder._order:
        desc = getattr(expr, "modifier", None) is operators.desc_op
        col = expr.element if hasattr(expr, "element") else expr
        specs.append((col, desc))
    return specs


def _encode_cursor(values: dict[str, Any], points_to_next: bool) -> str:
    payload = {**values, "_pointsToNextItems": points_to_next}
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()))


def _keyset_condition(specs: list[tuple[Any, bool]], values: dict[str, Any]) -> Any:
    from sqlalchemy import and_, or_

    clauses = []
    equal_so_far: list[Any] = []
    for col, desc in specs:
        value = values[col.key]
        cmp = (col < value) if desc else (col > value)
        clause = and_(*equal_so_far, cmp) if equal_so_far else cmp
        clauses.append(clause)
        equal_so_far = [*equal_so_far, col == value]
    return or_(*clauses)


class CursorPaginator(_BasePaginator):
    _has_more: bool
    _raw_cursor: str | None
    _specs: list[tuple[Any, bool]]

    @classmethod
    async def create(cls, builder: Builder[Any], per_page: int, cursor: str | None, page_name: str) -> CursorPaginator:
        specs = _order_spec(builder)
        req = _current_request()
        raw_cursor = cursor if cursor is not None else (req.query_params.get(page_name) if req is not None else None)
        points_to_next = True
        filtered = builder
        if raw_cursor:
            decoded = _decode_cursor(raw_cursor)
            points_to_next = bool(decoded.get("_pointsToNextItems", True))
            values = {k: v for k, v in decoded.items() if k != "_pointsToNextItems"}
            if points_to_next:
                filtered = builder.where(_keyset_condition(specs, values))
            else:
                reversed_specs = [(col, not desc) for col, desc in specs]
                filtered = builder.where(_keyset_condition(reversed_specs, values))
                filtered = filtered._clone(order=[(col.desc() if not desc else col.asc()) for col, desc in specs])
        rows = await filtered.limit(per_page + 1).get()
        has_more = len(rows) > per_page
        items = rows[:per_page]
        if raw_cursor and not points_to_next:
            items = list(reversed(items))
        paginator = cls(items, per_page, None, page_name)
        paginator._specs = specs
        paginator._has_more = has_more
        paginator._raw_cursor = raw_cursor
        return paginator

    def to_dict(self) -> dict[str, Any]:
        next_cursor = _encode_cursor({col.key: getattr(self.items[-1], col.key) for col, _ in self._specs}, True) if (self._has_more and self.items) else None
        prev_cursor = _encode_cursor({col.key: getattr(self.items[0], col.key) for col, _ in self._specs}, False) if (self._raw_cursor and self.items) else None
        return {
            "data": [_serialize(i) for i in self.items],
            "path": self._base_path(),
            "per_page": self.per_page,
            "next_cursor": next_cursor,
            "next_page_url": self._url_for(next_cursor),
            "prev_cursor": prev_cursor,
            "prev_page_url": self._url_for(prev_cursor),
        }
