"""Relationship helpers (T-33): `has_many`, `has_one`, `belongs_to`, `belongs_to_many`.

Each helper returns a SQLAlchemy `relationship(..., lazy="fastogram")`. A small registry, fed by
`register(cls)` (called from `Model.__init_subclass__` *before* `super().__init_subclass__()`, so
the raw `RelationshipProperty` objects are still sitting in `cls.__dict__`), pairs each `has_many`/
`has_one` with the matching `belongs_to` on the other side and sets `back_populates` on both
*before* SQLAlchemy configures either mapper — confirmed safe and sufficient to stop the
"will copy column ... conflicts with relationship(s)" warning and to make the pairing live
(setting `post.user = user` adds `post` to `user.posts` when loaded). `belongs_to_many` pairs the
same way, matching on the pivot table name.
"""

from __future__ import annotations

import re
import sys
from typing import Any

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import relationship

__all__ = ["belongs_to", "belongs_to_many", "has_many", "has_one", "model_by_name", "register"]

_pending: list[dict[str, Any]] = []
_registered_classes: dict[str, type] = {}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _caller_class_name() -> str | None:
    """The `__qualname__` of the class body that is calling the helper one frame up."""
    frame = sys._getframe(2)
    return frame.f_locals.get("__qualname__")


def _record(owner: str | None, kind: str, target: str, prop: Any, **meta: Any) -> Any:
    _pending.append({"owner": owner, "kind": kind, "target": target, "prop": prop, "name": None, **meta})
    return prop


def has_many(model: str, *, foreign_key: str | None = None, local_key: str = "id", order_by: str | None = None, **kw: Any) -> Any:
    owner = _caller_class_name()
    kwargs: dict[str, Any] = {"lazy": "fastogram"}
    if order_by is not None:
        kwargs["order_by"] = order_by
    kwargs.update(kw)
    prop = relationship(model, **kwargs)
    return _record(owner, "has_many", model, prop, foreign_key=foreign_key, local_key=local_key)


def has_one(model: str, *, foreign_key: str | None = None, local_key: str = "id", **kw: Any) -> Any:
    owner = _caller_class_name()
    kwargs: dict[str, Any] = {"lazy": "fastogram", "uselist": False}
    kwargs.update(kw)
    prop = relationship(model, **kwargs)
    return _record(owner, "has_one", model, prop, foreign_key=foreign_key, local_key=local_key)


def belongs_to(model: str, *, foreign_key: str | None = None, owner_key: str = "id", **kw: Any) -> Any:
    owner = _caller_class_name()
    kwargs: dict[str, Any] = {"lazy": "fastogram"}
    kwargs.update(kw)
    prop = relationship(model, **kwargs)
    return _record(owner, "belongs_to", model, prop, foreign_key=foreign_key, owner_key=owner_key)


def belongs_to_many(
    model: str,
    *,
    table: str | None = None,
    foreign_pivot_key: str | None = None,
    related_pivot_key: str | None = None,
    order_by: str | None = None,
    **kw: Any,
) -> Any:
    owner = _caller_class_name()
    kwargs: dict[str, Any] = {"lazy": "fastogram"}
    if order_by is not None:
        kwargs["order_by"] = order_by
    kwargs.update(kw)
    # The pivot's own table is resolved lazily, once both class names are known, because its
    # columns reference each side's table by name only (no need to wait for mapping).
    pivot_name = table or "_".join(sorted((_snake(owner or ""), _snake(model))))
    fk_pivot = foreign_pivot_key or f"{_snake(owner or '')}_id"
    related_pivot = related_pivot_key or f"{_snake(model)}_id"
    secondary = _pivot_table(pivot_name, owner or "", fk_pivot, model, related_pivot)
    kwargs.setdefault("secondary", secondary)
    prop = relationship(model, **kwargs)
    return _record(owner, "belongs_to_many", model, prop, pivot=pivot_name, fk=fk_pivot, related_fk=related_pivot)


def _pivot_table(name: str, owner: str, owner_fk: str, target: str, target_fk: str) -> Table:
    from fastogram.database.model import Model, table_name_for

    existing = Model.metadata.tables.get(name)
    if existing is not None:
        return existing
    return Table(
        name,
        Model.metadata,
        Column(owner_fk, ForeignKey(f"{table_name_for(owner)}.id", ondelete="CASCADE"), primary_key=True),
        Column(target_fk, ForeignKey(f"{table_name_for(target)}.id", ondelete="CASCADE"), primary_key=True),
    )


def model_by_name(name: str) -> type | None:
    return _registered_classes.get(name)


def register(cls: type) -> None:
    """Called from `Model.__init_subclass__` before SQLAlchemy replaces the class attributes."""
    _registered_classes[cls.__name__] = cls
    for key, value in list(vars(cls).items()):
        for item in _pending:
            if item["prop"] is value and item["name"] is None and item["owner"] == cls.__name__:
                item["name"] = key
    _try_pair()


def _try_pair() -> None:
    for a in _pending:
        if a["name"] is None or a["prop"].back_populates:
            continue
        if a["kind"] in ("has_many", "has_one"):
            _pair_to_one(a)
        elif a["kind"] == "belongs_to_many":
            _pair_many_to_many(a)


def _pair_to_one(a: dict[str, Any]) -> None:
    fk_a = a["foreign_key"] or f"{_snake(a['owner'] or '')}_id"
    for b in _pending:
        if b["kind"] != "belongs_to" or b["name"] is None or b["prop"].back_populates:
            continue
        if a["target"] != b["owner"] or b["target"] != a["owner"]:
            continue
        fk_b = b["foreign_key"] or f"{b['name']}_id"
        if fk_a != fk_b:
            continue
        a["prop"].back_populates = b["name"]
        b["prop"].back_populates = a["name"]


def _pair_many_to_many(a: dict[str, Any]) -> None:
    for b in _pending:
        if b["kind"] != "belongs_to_many" or b["name"] is None or b["prop"].back_populates:
            continue
        if a["target"] != b["owner"] or b["target"] != a["owner"]:
            continue
        if a["pivot"] != b["pivot"]:
            continue
        a["prop"].back_populates = b["name"]
        b["prop"].back_populates = a["name"]
