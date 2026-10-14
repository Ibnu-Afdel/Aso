"""`Builder[T]`: the fluent query builder (T-32).

Generative: every method returns a **new** `Builder` (the filters/ordering/options are plain
Python state on the builder, not accumulated onto a shared `Select`), so a base query can be
reused safely (`base = Post.published(); await base.latest().get(); await base.count()`).

`Model.__getattr__` (class-level, via `ModelMeta`) forwards any name this class does not define
itself to `cls.query().<name>`, which is how `Post.where(...)`, `Post.latest()`, `Post.with_(...)`
etc. all work as class-level shortcuts without hand-written boilerplate per method.
"""

from __future__ import annotations

import inspect as _inspect
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy import exists as sa_exists
from sqlalchemy import update as sa_update
from sqlalchemy.orm import selectinload, with_parent
from sqlalchemy.sql import Select

from fastogram.exceptions.types import ModelNotFound, MultipleRecordsFound

__all__ = ["Builder", "RelationBuilder"]

log = logging.getLogger("fastogram.database")

T = TypeVar("T")


def _pk_column(model: type) -> Any:
    from sqlalchemy import inspect as sa_inspect

    return sa_inspect(model).primary_key[0]


def _session() -> Any:
    from fastogram.database.scope import current_scope

    return current_scope().session()


async def _write(fn: Callable[[Any], Any]) -> Any:
    from fastogram.database.scope import write

    return await write(fn)


class Builder(Generic[T]):
    def __init__(self, model: type[T]) -> None:
        self.model = model
        self._where: Any = None
        self._order: list[Any] = []
        self._random = False
        self._limit: int | None = None
        self._offset: int | None = None
        self._distinct = False
        self._options: list[Any] = []
        self._from_stmt: Select | None = None
        self._with_trashed = False
        self._only_trashed = False
        self._with_count_specs: list[tuple[str, Callable[[Builder], Builder] | None]] = []
        self._through: Callable[[Any], Any] | None = None

    # ------------------------------------------------------------ cloning

    def _clone(self, **overrides: Any) -> Builder[T]:
        new = Builder.__new__(type(self))
        new.model = self.model
        new._where = overrides.get("where", self._where)
        new._order = overrides.get("order", self._order)
        new._random = overrides.get("random", self._random)
        new._limit = overrides.get("limit", self._limit)
        new._offset = overrides.get("offset", self._offset)
        new._distinct = overrides.get("distinct", self._distinct)
        new._options = overrides.get("options", self._options)
        new._from_stmt = overrides.get("from_stmt", self._from_stmt)
        new._with_trashed = overrides.get("with_trashed", self._with_trashed)
        new._only_trashed = overrides.get("only_trashed", self._only_trashed)
        new._with_count_specs = overrides.get("with_count_specs", self._with_count_specs)
        new._through = overrides.get("through", self._through)
        if isinstance(self, RelationBuilder):
            new.owner = self.owner  # type: ignore[attr-defined]
            new.rel_name = self.rel_name  # type: ignore[attr-defined]
            new._rel_attr = self._rel_attr  # type: ignore[attr-defined]
        return new

    # ------------------------------------------------------------ building the statement

    @property
    def statement(self) -> Select:
        stmt = self._from_stmt if self._from_stmt is not None else select(self.model)
        if self._where is not None:
            stmt = stmt.where(self._where)
        if self._distinct:
            stmt = stmt.distinct()
        if self._random:
            stmt = stmt.order_by(func.random())
        elif self._order:
            stmt = stmt.order_by(*self._order)
        if self._limit is not None:
            stmt = stmt.limit(self._limit)
        if self._offset is not None:
            stmt = stmt.offset(self._offset)
        if self._options:
            stmt = stmt.options(*self._options)
        return stmt

    def _final_statement(self) -> Select:
        return self.statement.execution_options(with_trashed=self._with_trashed, only_trashed=self._only_trashed)

    def to_sql(self) -> str:
        return str(self.statement)

    def from_statement(self, stmt: Select) -> Builder[T]:
        return self._clone(from_stmt=stmt, where=None, order=[], limit=None, offset=None)

    # ------------------------------------------------------------ where

    def _group_clause(self, fn: Callable[[Builder[T]], Builder[T]]) -> Any:
        sub = fn(Builder(self.model))
        return sub._where if sub._where is not None else literal(True)

    def _combine(self, args: tuple[Any, ...], eq: dict[str, Any]) -> Any:
        conditions = [self._group_clause(a) if callable(a) else a for a in args]
        conditions += [getattr(self.model, k) == v for k, v in eq.items()]
        if not conditions:
            return None
        return conditions[0] if len(conditions) == 1 else and_(*conditions)

    def where(self, *args: Any, **eq: Any) -> Builder[T]:
        new = self._combine(args, eq)
        if new is None:
            return self
        return self._clone(where=new if self._where is None else and_(self._where, new))

    def or_where(self, *args: Any, **eq: Any) -> Builder[T]:
        new = self._combine(args, eq)
        if new is None:
            return self
        return self._clone(where=new if self._where is None else or_(self._where, new))

    def where_in(self, column: Any, values: Any) -> Builder[T]:
        return self.where(column.in_(list(values)))

    def where_not_in(self, column: Any, values: Any) -> Builder[T]:
        return self.where(column.not_in(list(values)))

    def where_null(self, column: Any) -> Builder[T]:
        return self.where(column.is_(None))

    def where_not_null(self, column: Any) -> Builder[T]:
        return self.where(column.is_not(None))

    def where_between(self, column: Any, low: Any, high: Any) -> Builder[T]:
        return self.where(column.between(low, high))

    def where_date(self, column: Any, value: Any) -> Builder[T]:
        from sqlalchemy import Date, cast

        return self.where(cast(column, Date) == value)

    def when(self, value: Any, fn: Callable[..., Any], default: Callable[..., Any] | None = None) -> Builder[T]:
        chosen = fn if value else default
        if chosen is None:
            return self
        n = len(_inspect.signature(chosen).parameters)
        result = chosen(self, value) if n >= 2 else chosen(self)
        return result if result is not None else self

    def unless(self, value: Any, fn: Callable[..., Any], default: Callable[..., Any] | None = None) -> Builder[T]:
        return self.when(not value, fn, default)

    # ------------------------------------------------------------ ordering, limiting

    def order_by(self, column: Any, direction: str = "asc") -> Builder[T]:
        expr = column.desc() if direction == "desc" else column.asc() if direction == "asc" else column
        return self._clone(order=[*self._order, expr], random=False)

    def latest(self, column: Any = None) -> Builder[T]:
        return self.order_by(column if column is not None else self.model.created_at, "desc")

    def oldest(self, column: Any = None) -> Builder[T]:
        return self.order_by(column if column is not None else self.model.created_at, "asc")

    def in_random_order(self) -> Builder[T]:
        return self._clone(order=[], random=True)

    def reorder(self, column: Any = None, direction: str = "asc") -> Builder[T]:
        cleared = self._clone(order=[], random=False)
        return cleared if column is None else cleared.order_by(column, direction)

    def limit(self, n: int) -> Builder[T]:
        return self._clone(limit=n)

    def offset(self, n: int) -> Builder[T]:
        return self._clone(offset=n)

    take = limit
    skip = offset

    def for_page(self, page: int, per_page: int) -> Builder[T]:
        page = max(1, page)
        return self._clone(limit=per_page, offset=(page - 1) * per_page)

    def distinct(self) -> Builder[T]:
        return self._clone(distinct=True)

    def through(self, fn: Callable[[Any], Any]) -> Builder[T]:
        return self._clone(through=fn)

    # ------------------------------------------------------------ soft deletes (T-31)

    def with_trashed(self) -> Builder[T]:
        return self._clone(with_trashed=True)

    def only_trashed(self) -> Builder[T]:
        return self._clone(only_trashed=True)

    # ------------------------------------------------------------ relationships (T-33)

    def with_(self, *paths: str | dict[str, Any]) -> Builder[T]:
        options = list(self._options)
        for path in paths:
            if isinstance(path, dict):
                for key, constraint in path.items():
                    options.append(self._load_option(key, constraint))
            else:
                options.append(self._load_option(path, None))
        return self._clone(options=options)

    def _load_option(self, path: str, constraint: Callable[[Builder[Any]], Builder[Any]] | None) -> Any:
        parts = path.split(".")
        model = self.model
        loader = None
        for i, part in enumerate(parts):
            attr = getattr(model, part)
            step = selectinload(attr) if loader is None else loader.selectinload(attr)
            if i == len(parts) - 1 and constraint is not None:
                sub = constraint(Builder(attr.property.mapper.class_))
                if sub._order:
                    raise ValueError(
                        f'with_("{path}") cannot order inside the constraint. Use a fixed '
                        f"order_by= on the relationship helper, or query through relation(...)."
                    )
                if sub._where is not None:
                    step = selectinload(attr).and_(sub._where) if loader is None else loader.selectinload(attr).and_(sub._where)
            loader = step
            model = attr.property.mapper.class_
        return loader

    def with_count(self, *specs: str | dict[str, Any]) -> Builder[T]:
        items = list(self._with_count_specs)
        for spec in specs:
            if isinstance(spec, dict):
                items.extend(spec.items())
            else:
                items.append((spec, None))
        return self._clone(with_count_specs=items)

    def where_has(self, path: str, constraint: Callable[[Builder[Any]], Builder[Any]] | None = None) -> Builder[T]:
        return self.where(_has_clause(self.model, path.split("."), constraint))

    def doesnt_have(self, path: str, constraint: Callable[[Builder[Any]], Builder[Any]] | None = None) -> Builder[T]:
        return self.where(~_has_clause(self.model, path.split("."), constraint))

    # ------------------------------------------------------------ terminal methods

    async def get(self) -> list[T]:
        result = await _session().scalars(self._final_statement())
        items = list(result.unique().all())
        await self._apply_with_count(items)
        if self._through is not None:
            items = [self._through(i) for i in items]
        return items

    async def _apply_with_count(self, items: list[Any]) -> None:
        if not self._with_count_specs or not items:
            return
        pk = _pk_column(self.model)
        ids = [getattr(obj, pk.key) for obj in items]
        session = _session()
        for name, constraint in self._with_count_specs:
            rel_attr = getattr(self.model, name)
            related_model = rel_attr.property.mapper.class_
            local_col, remote_col = rel_attr.property.local_remote_pairs[0]
            q = select(remote_col, func.count())
            if constraint is not None:
                sub = constraint(Builder(related_model))
                if sub._where is not None:
                    q = q.where(sub._where)
            q = q.where(remote_col.in_(ids)).group_by(remote_col)
            counts = dict((await session.execute(q)).all())
            for obj in items:
                setattr(obj, f"{name}_count", counts.get(getattr(obj, pk.key), 0))

    async def first(self) -> T | None:
        builder = self if self._limit is not None else self.limit(1)
        items = await builder.get()
        return items[0] if items else None

    async def first_or_fail(self) -> T:
        obj = await self.first()
        if obj is None:
            raise ModelNotFound(self.model.__name__)
        return obj

    async def sole(self) -> T:
        items = await self.limit(2).get()
        if not items:
            raise ModelNotFound(self.model.__name__)
        if len(items) > 1:
            raise MultipleRecordsFound(len(items))
        return items[0]

    async def find(self, id_: Any) -> T | None:
        pk = _pk_column(self.model)
        return await self.where(pk == id_).first()

    async def value(self, column: Any) -> Any:
        stmt = self._final_statement().order_by(None).with_only_columns(column).limit(1)
        return await _session().scalar(stmt)

    async def pluck(self, column: Any, key: Any = None) -> Any:
        cols = (key, column) if key is not None else (column,)
        stmt = self._final_statement().order_by(None).with_only_columns(*cols)
        rows = (await _session().execute(stmt)).all()
        if key is not None:
            return {row[0]: row[1] for row in rows}
        return [row[0] for row in rows]

    async def count(self) -> int:
        subq = self._final_statement().order_by(None).subquery()
        return int(await _session().scalar(select(func.count()).select_from(subq)) or 0)

    async def exists(self) -> bool:
        stmt = select(sa_exists(self._final_statement().order_by(None)))
        return bool(await _session().scalar(stmt))

    async def doesnt_exist(self) -> bool:
        return not await self.exists()

    async def _scalar_agg(self, expr: Any) -> Any:
        stmt = self._final_statement().order_by(None).with_only_columns(expr)
        return await _session().scalar(stmt)

    async def sum(self, column: Any) -> Any:
        return await self._scalar_agg(func.sum(column))

    async def avg(self, column: Any) -> Any:
        return await self._scalar_agg(func.avg(column))

    async def min(self, column: Any) -> Any:
        return await self._scalar_agg(func.min(column))

    async def max(self, column: Any) -> Any:
        return await self._scalar_agg(func.max(column))

    # ------------------------------------------------------------ bulk writes

    async def update(self, **values: Any) -> int:
        model = self.model
        data = dict(values)
        if getattr(model, "__timestamps__", True) and "updated_at" not in data:
            data["updated_at"] = datetime.now(UTC)
        stmt = sa_update(model).execution_options(synchronize_session="fetch")
        if self._where is not None:
            stmt = stmt.where(self._where)
        stmt = stmt.values(**data)

        async def run(session: Any) -> int:
            result = await session.execute(stmt)
            return int(result.rowcount)

        return await _write(run)

    async def delete(self) -> int:
        if getattr(self.model, "__soft_deletes__", False):
            return await self.update(deleted_at=datetime.now(UTC))
        stmt = sa_delete(self.model).execution_options(synchronize_session="fetch")
        if self._where is not None:
            stmt = stmt.where(self._where)

        async def run(session: Any) -> int:
            result = await session.execute(stmt)
            return int(result.rowcount)

        return await _write(run)

    async def increment(self, column: Any, by: int = 1, **extra: Any) -> int:
        return await self.update(**{column.key: column + by}, **extra)

    async def decrement(self, column: Any, by: int = 1, **extra: Any) -> int:
        return await self.update(**{column.key: column - by}, **extra)

    # ------------------------------------------------------------ chunking

    async def chunk(self, n: int) -> AsyncIterator[list[T]]:
        if self._order or self._random:
            log.warning("chunk() without a plain order_by(pk) pages with limit/offset; rows may shift mid-iteration.")
            builder = self
        else:
            builder = self.order_by(_pk_column(self.model))
        offset = 0
        while True:
            page = await builder.limit(n).offset(offset).get()
            if not page:
                return
            yield page
            if len(page) < n:
                return
            offset += n

    async def lazy(self, n: int = 1000) -> AsyncIterator[T]:
        async for page in self.chunk(n):
            for item in page:
                yield item

    # ------------------------------------------------------------ pagination (T-34)

    async def paginate(self, per_page: int = 15, page: int | None = None, page_name: str = "page") -> Any:
        from fastogram.database.pagination import LengthAwarePaginator

        return await LengthAwarePaginator.create(self, per_page, page, page_name)

    async def simple_paginate(self, per_page: int = 15, page: int | None = None, page_name: str = "page") -> Any:
        from fastogram.database.pagination import SimplePaginator

        return await SimplePaginator.create(self, per_page, page, page_name)

    async def cursor_paginate(self, per_page: int = 15, cursor: str | None = None, page_name: str = "cursor") -> Any:
        from fastogram.database.pagination import CursorPaginator

        return await CursorPaginator.create(self, per_page, cursor, page_name)


def _has_clause(model: type, parts: list[str], constraint: Callable[[Builder[Any]], Builder[Any]] | None) -> Any:
    rel_attr = getattr(model, parts[0])
    related_model = rel_attr.property.mapper.class_
    if len(parts) > 1:
        inner = _has_clause(related_model, parts[1:], constraint)
    else:
        inner = None
        if constraint is not None:
            sub = constraint(Builder(related_model))
            inner = sub._where
    if rel_attr.property.uselist:
        return rel_attr.any(inner) if inner is not None else rel_attr.any()
    return rel_attr.has(inner) if inner is not None else rel_attr.has()


class RelationBuilder(Builder[T]):
    """`post.relation("comments")`: a `Builder` pre-filtered to one parent instance (T-33)."""

    def __init__(self, owner: Any, name: str) -> None:
        rel_attr = getattr(type(owner), name)
        super().__init__(rel_attr.property.mapper.class_)
        self.owner = owner
        self.rel_name = name
        self._rel_attr = rel_attr
        self._where = with_parent(owner, rel_attr)

    async def create(self, **data: Any) -> Any:
        payload = dict(data)
        prop = self._rel_attr.property
        if prop.secondary is None:
            local_col, remote_col = prop.local_remote_pairs[0]
            payload[remote_col.key] = getattr(self.owner, local_col.key)
            obj = await self.model.create(**payload)
        else:
            obj = await self.model.create(**payload)
            await self.attach([getattr(obj, _pk_column(self.model).key)])
        return obj

    async def create_many(self, rows: list[dict[str, Any]]) -> list[Any]:
        return [await self.create(**row) for row in rows]

    # ------------------------------------------------------------ many-to-many

    def _pivot(self) -> tuple[Any, Any, Any]:
        prop = self._rel_attr.property
        pivot = prop.secondary
        owner_pk = _pk_column(type(self.owner))
        owner_value = getattr(self.owner, owner_pk.key)
        local_pairs = {remote.name: local for local, remote in prop.synchronize_pairs}
        owner_col = None
        related_col = None
        for col in pivot.columns:
            if col.name in local_pairs:
                owner_col = col
            else:
                related_col = col
        if owner_col is None or related_col is None:  # pragma: no cover - defensive
            raise RuntimeError(f"Could not resolve pivot columns for {self.rel_name!r}.")
        return pivot, owner_col, related_col, owner_value

    async def attach(self, ids: Any) -> None:
        pivot, owner_col, related_col, owner_value = self._pivot()
        ids = _as_id_list(ids)
        if not ids:
            return

        async def run(session: Any) -> None:
            existing = {
                row[0]
                for row in (
                    await session.execute(
                        select(related_col).where(owner_col == owner_value, related_col.in_(ids))
                    )
                ).all()
            }
            new_ids = [i for i in ids if i not in existing]
            if new_ids:
                await session.execute(pivot.insert(), [{owner_col.name: owner_value, related_col.name: i} for i in new_ids])

        await _write(run)

    async def detach(self, ids: Any = None) -> None:
        pivot, owner_col, related_col, owner_value = self._pivot()

        async def run(session: Any) -> None:
            stmt = pivot.delete().where(owner_col == owner_value)
            if ids is not None:
                stmt = stmt.where(related_col.in_(_as_id_list(ids)))
            await session.execute(stmt)

        await _write(run)

    async def sync(self, ids: Any) -> dict[str, list[Any]]:
        pivot, owner_col, related_col, owner_value = self._pivot()
        ids = set(_as_id_list(ids))

        async def run(session: Any) -> dict[str, list[Any]]:
            current = {
                row[0]
                for row in (await session.execute(select(related_col).where(owner_col == owner_value))).all()
            }
            to_attach = sorted(ids - current)
            to_detach = sorted(current - ids)
            if to_detach:
                await session.execute(pivot.delete().where(owner_col == owner_value, related_col.in_(to_detach)))
            if to_attach:
                await session.execute(pivot.insert(), [{owner_col.name: owner_value, related_col.name: i} for i in to_attach])
            return {"attached": to_attach, "detached": to_detach}

        return await _write(run)

    async def toggle(self, ids: Any) -> dict[str, list[Any]]:
        pivot, owner_col, related_col, owner_value = self._pivot()
        ids = _as_id_list(ids)

        async def run(session: Any) -> dict[str, list[Any]]:
            current = {
                row[0]
                for row in (
                    await session.execute(select(related_col).where(owner_col == owner_value, related_col.in_(ids)))
                ).all()
            }
            to_attach = [i for i in ids if i not in current]
            to_detach = [i for i in ids if i in current]
            if to_detach:
                await session.execute(pivot.delete().where(owner_col == owner_value, related_col.in_(to_detach)))
            if to_attach:
                await session.execute(pivot.insert(), [{owner_col.name: owner_value, related_col.name: i} for i in to_attach])
            return {"attached": to_attach, "detached": to_detach}

        return await _write(run)


def _as_id_list(ids: Any) -> list[Any]:
    if isinstance(ids, (list, tuple, set)):
        return list(ids)
    return [ids]
