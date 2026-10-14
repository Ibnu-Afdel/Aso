"""`Model`: Eloquent-style base class over SQLAlchemy 2.1 (T-31).

Table naming, `id`/timestamps, mass assignment, serialisation, dirty tracking, soft deletes,
`HasUuids`/`HasUlids`, and the class-level query-builder forwarding (`Post.where(...)` etc, via
`ModelMeta.__getattr__`) all live here. The query builder itself is `fastogram.database.builder`.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar, Self

import inflect
from sqlalchemy import BigInteger, Integer, event, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    decl_api,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.strategies import _LazyLoader  # private: pinned sqlalchemy >=2.1.4,<2.2 (S-2)

from fastogram.database import relationships as _rel
from fastogram.database.scope import current_scope, write
from fastogram.database.types import UtcDateTime, ulid, uuid7
from fastogram.exceptions.types import (
    LazyLoadingViolation,
    MassAssignmentError,
    ModelNotFound,
)

log = logging.getLogger("fastogram.database")
_inflect = inflect.engine()

_UNCOUNTABLE = {"media", "news", "equipment", "information", "series", "species", "data"}


def table_name_for(class_name: str) -> str:
    """`BlogPost` → `blog_posts` (snake_case plural, like Laravel)."""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    parts = snake.split("_")
    last = parts[-1]
    parts[-1] = last if last in _UNCOUNTABLE else (_inflect.plural_noun(last) or last)
    return "_".join(parts)


@RelationshipProperty.strategy_for(lazy="fastogram")
class _PreventLazyLoader(_LazyLoader):
    """`lazy="raise"` with Laravel's `preventLazyLoading` message (S-2)."""

    def __init__(self, parent: Any, strategy_key: Any) -> None:
        super().__init__(parent, strategy_key)
        self._raise_always = True

    def _invoke_raise_load(self, state: Any, passive: Any, lazy: Any) -> None:
        raise LazyLoadingViolation(state.class_.__name__, self.key)


class ModelMeta(decl_api.DeclarativeAttributeIntercept):
    """Forwards any class attribute this class does not define to `cls.query()` (T-32).

    This is how `Post.where(...)`, `Post.latest()`, `Post.with_(...)` etc. all work without one
    classmethod per builder method: Python only calls `__getattr__` once normal lookup fails.
    """

    def __getattr__(cls, name: str) -> Any:  # noqa: N805
        if name.startswith("_") or name in ("query", "metadata", "registry"):
            raise AttributeError(name)
        try:
            query = cls.query()  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc
        return getattr(query, name)


class Model(AsyncAttrs, DeclarativeBase, metaclass=ModelMeta):
    __abstract__ = True
    __timestamps__: ClassVar[bool] = True
    __fillable__: ClassVar[list[str] | None] = None
    __guarded__: ClassVar[list[str] | None] = None
    __hidden__: ClassVar[tuple[str, ...]] = ()
    __appends__: ClassVar[tuple[str, ...]] = ()
    __touches__: ClassVar[tuple[str, ...]] = ()
    __soft_deletes__: ClassVar[bool] = False

    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UtcDateTime}

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return table_name_for(cls.__name__)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Capture raw relationship()s (and pair has_many/belongs_to by convention) before
        # SQLAlchemy's own __init_subclass__ (called via super() below) replaces them.
        _rel.register(cls)
        if not cls.__dict__.get("__abstract__", False):
            _add_primary_key(cls)
            _add_timestamps(cls)
        super().__init_subclass__(**kwargs)

    # ------------------------------------------------------------ querying (forwarded, see ModelMeta)

    @classmethod
    def query(cls) -> Any:
        from fastogram.database.builder import Builder

        return Builder(cls)

    # ------------------------------------------------------------ reading

    @classmethod
    async def find(cls, id_: Any) -> Self | None:
        # Routed through the Builder (not `session.get()`) so the SoftDeletes default scope and
        # `with_trashed()`/`only_trashed()` apply; `session.get()` bypasses `do_orm_execute`.
        return await cls.query().find(id_)

    @classmethod
    async def find_or_fail(cls, id_: Any) -> Self:
        obj = await cls.find(id_)
        if obj is None:
            raise ModelNotFound(cls.__name__, [id_])
        return obj

    @classmethod
    async def find_many(cls, ids: Any) -> list[Self]:
        pk = _pk_column(cls)
        return await cls.query().where(pk.in_(list(ids))).get()

    @classmethod
    async def first_where(cls, *args: Any, **eq: Any) -> Self | None:
        return await cls.query().where(*args, **eq).first()

    @classmethod
    async def all(cls) -> list[Self]:
        return await cls.query().get()

    @classmethod
    async def count(cls) -> int:
        # Routed through the Builder (not a bare `select(func.count()).select_from(cls)`), same
        # reason as `find()`: a plain Core-style count selects no ORM entity, so SQLAlchemy never
        # treats it as ORM-enabled and the SoftDeletes `do_orm_execute` default-scope hook (which
        # only fires for statements carrying a mapper) never runs, silently counting trashed rows.
        return await cls.query().count()

    @classmethod
    async def first_or_create(cls, attributes: dict[str, Any], values: dict[str, Any] | None = None) -> Self:
        existing = await cls.query().where(**attributes).first()
        if existing is not None:
            return existing
        # `values` may repeat a key from `attributes` (Laravel allows this; values win), so merge
        # into one dict instead of `cls.create(**attributes, **values)`, which raises
        # "got multiple values for keyword argument" on any overlapping key.
        return await cls.create(**{**attributes, **(values or {})})

    @classmethod
    async def update_or_create(cls, attributes: dict[str, Any], values: dict[str, Any] | None = None) -> Self:
        existing = await cls.query().where(**attributes).first()
        if existing is not None:
            return await existing.update(**(values or {}))
        return await cls.create(**{**attributes, **(values or {})})

    # ------------------------------------------------------------ mass assignment (T-31)

    @classmethod
    def _fillable_keys(cls) -> set[str] | None:
        """`None` means unrestricted: neither `__fillable__` nor `__guarded__` was declared."""
        if cls.__fillable__ is not None:
            return set(cls.__fillable__)
        if cls.__guarded__ is not None:
            all_keys = set(_column_attr_names(cls)) | set(cls.__mapper__.relationships.keys())
            return all_keys - set(cls.__guarded__)
        return None

    @classmethod
    def _mass_assign(cls, data: dict[str, Any]) -> dict[str, Any]:
        fillable = cls._fillable_keys()
        if fillable is None:
            return dict(data)
        allowed: dict[str, Any] = {}
        blocked: list[str] = []
        for key, value in data.items():
            if key in fillable:
                allowed[key] = value
            else:
                blocked.append(key)
        if blocked:
            from fastogram.config import config

            if config("app.environment", "production") in ("local", "testing"):
                raise MassAssignmentError(
                    f"Add [{', '.join(blocked)}] to {cls.__name__}.__fillable__ (or remove it from "
                    f"__guarded__) to mass assign it."
                )
            log.warning("Mass assignment of non-fillable attribute(s) on %s: %s (dropped)", cls.__name__, blocked)
        return allowed

    @classmethod
    async def create(cls, **data: Any) -> Self:
        obj = cls(**cls._mass_assign(data))
        await obj.save()
        return obj

    def fill(self, **data: Any) -> Self:
        allowed = type(self)._mass_assign(data)
        valid = set(_column_attr_names(type(self))) | set(type(self).__mapper__.relationships.keys())
        for key, value in allowed.items():
            if key not in valid:
                raise AttributeError(f"{type(self).__name__} has no column or relation {key!r}.")
            setattr(self, key, value)
        return self

    # ------------------------------------------------------------ writing (savepoint + autocommit, T-30)

    async def save(self) -> Self:
        state = sa_inspect(self)
        is_new = state.transient or state.pending
        if not is_new and not self.is_dirty():
            return self
        changed = {name for name in _column_attr_names(type(self)) if self.is_dirty(name)}
        if type(self).__timestamps__:
            now = datetime.now(UTC)
            if is_new and getattr(self, "created_at", None) is None:
                self.created_at = now
                changed.add("created_at")
            self.updated_at = now
            changed.add("updated_at")
        await write(lambda session: session.add(self))
        self._fastogram_changes = dict.fromkeys(changed, True)
        await self._touch_parents()
        return self

    async def _touch_parents(self) -> None:
        for name in type(self).__touches__:
            if self.relation_loaded(name):
                parent = getattr(self, name)
                if parent is not None and type(parent).__timestamps__:
                    parent.updated_at = datetime.now(UTC)
                    await write(lambda session, p=parent: session.add(p))

    async def update(self, **data: Any) -> Self:
        self.fill(**data)
        return await self.save()

    async def delete(self) -> None:
        async def _delete(session: Any) -> None:
            await session.delete(self)

        await write(_delete)

    @classmethod
    async def destroy(cls, ids: Any) -> int:
        id_list = list(ids) if isinstance(ids, (list, tuple, set)) else [ids]
        count = 0
        for id_ in id_list:
            obj = await cls.find(id_)
            if obj is not None:
                await obj.delete()
                count += 1
        return count

    # ------------------------------------------------------------ refreshing (T-31)

    async def refresh(self) -> Self:
        state = sa_inspect(self)
        loaded_relations = [k for k in type(self).__mapper__.relationships.keys() if k not in state.unloaded]
        session = current_scope().session()
        if loaded_relations:
            await session.refresh(self, attribute_names=loaded_relations)
        else:
            await session.refresh(self)
        return self

    async def fresh(self) -> Self:
        return await self.refresh()

    # ------------------------------------------------------------ dirty checking (T-31)

    def is_dirty(self, *keys: str) -> bool:
        state = sa_inspect(self)
        names = keys or tuple(_column_attr_names(type(self)))
        for name in names:
            history = state.attrs[name].history
            if history.added or history.deleted:
                return True
        return False

    def was_changed(self, *keys: str) -> bool:
        changes = getattr(self, "_fastogram_changes", None) or {}
        if not keys:
            return bool(changes)
        return any(k in changes for k in keys)

    def get_original(self, key: str | None = None) -> Any:
        state = sa_inspect(self)
        if key is None:
            return {name: self._original(state, name) for name in _column_attr_names(type(self))}
        return self._original(state, key)

    @staticmethod
    def _original(state: Any, key: str) -> Any:
        history = state.attrs[key].history
        if history.deleted:
            return history.deleted[0]
        if history.unchanged:
            return history.unchanged[0]
        return None

    # ------------------------------------------------------------ comparing (T-31)

    def is_(self, other: Any) -> bool:
        if not isinstance(other, Model) or type(self) is not type(other):
            return False
        pk = _pk_attr_name(type(self))
        return getattr(self, pk) == getattr(other, pk)

    def is_not(self, other: Any) -> bool:
        return not self.is_(other)

    # ------------------------------------------------------------ serialisation (T-31)

    def only(self, *keys: str) -> dict[str, Any]:
        return {k: _jsonable(getattr(self, k)) for k in keys}

    def make_hidden(self, *keys: str) -> Self:
        self._fastogram_hidden_extra = set(getattr(self, "_fastogram_hidden_extra", ())) | set(keys)
        return self

    def make_visible(self, *keys: str) -> Self:
        self._fastogram_visible_extra = set(getattr(self, "_fastogram_visible_extra", ())) | set(keys)
        return self

    def to_dict(self) -> dict[str, Any]:
        hidden = set(self.__hidden__) | set(getattr(self, "_fastogram_hidden_extra", ()))
        hidden -= set(getattr(self, "_fastogram_visible_extra", ()))
        state = sa_inspect(self)
        data: dict[str, Any] = {}
        for name in _column_attr_names(type(self)):
            if name not in hidden:
                data[name] = _jsonable(getattr(self, name))
        for name in self.__appends__:
            if name not in hidden:
                data[name] = _jsonable(getattr(self, name))
        for name in type(self).__mapper__.relationships.keys():
            if name in hidden or name in state.unloaded:
                continue
            value = getattr(self, name)
            if isinstance(value, list):
                data[name] = [v.to_dict() if hasattr(v, "to_dict") else v for v in value]
            else:
                data[name] = value.to_dict() if hasattr(value, "to_dict") else value
        return data

    # ------------------------------------------------------------ relationships (T-33)

    def relation(self, name: str) -> Any:
        from fastogram.database.builder import RelationBuilder

        return RelationBuilder(self, name)

    def relation_loaded(self, name: str) -> bool:
        return name not in sa_inspect(self).unloaded

    async def load(self, *names: str) -> Self:
        from fastogram.database.builder import Builder

        session = current_scope().session()
        if all("." not in n for n in names):
            await session.refresh(self, attribute_names=list(names))
            return self
        pk = _pk_column(type(self))
        options = [Builder(type(self))._load_option(n, None) for n in names]
        stmt = select(type(self)).where(pk == getattr(self, pk.key)).options(*options).execution_options(populate_existing=True)
        await session.execute(stmt)
        return self

    async def load_missing(self, *names: str) -> Self:
        missing = [n for n in names if not self.relation_loaded(n.split(".")[0])]
        if missing:
            await self.load(*missing)
        return self


def _pk_column(model: type) -> Any:
    return sa_inspect(model).primary_key[0]


def _column_attr_names(model: type) -> list[str]:
    """The mapped Python attribute names of every column, in declaration order.

    Not `[c.key for c in model.__table__.columns]`: a `Column.key` is the *database* column
    name, which only equals the mapped attribute name by convention. `mapped_column("type",
    ...)` on an attribute named `type_` (common for columns that would otherwise shadow a Python
    builtin) breaks that convention, and every one of `save()`'s dirty-set, `is_dirty()`'s
    default keys, `get_original()` and `to_dict()` used to read/write the wrong name in that case
    (`getattr(self, "type")` instead of `getattr(self, "type_")`), raising `AttributeError` or
    silently producing an empty dirty-set. `Mapper.column_attrs[*].key` is the attribute name.
    """
    return [prop.key for prop in sa_inspect(model).mapper.column_attrs]


def _pk_attr_name(model: type) -> str:
    """The mapped Python attribute name of the primary key column (see `_column_attr_names`)."""
    return sa_inspect(model).mapper.get_property_by_column(_pk_column(model)).key


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _has_custom_primary_key(cls: type) -> bool:
    return any("id" in base.__dict__ for base in cls.__mro__ if base not in (Model, object))


def _add_primary_key(cls: type) -> None:
    if _has_custom_primary_key(cls):
        return
    id_type = BigInteger().with_variant(Integer(), "sqlite")
    cls.id = mapped_column(id_type, primary_key=True, autoincrement=True)
    cls.__annotations__ = {**getattr(cls, "__annotations__", {}), "id": Mapped[int]}


def _add_timestamps(cls: type) -> None:
    if not cls.__dict__.get("__timestamps__", getattr(cls, "__timestamps__", True)):
        return
    if "created_at" not in cls.__dict__ and "created_at" not in getattr(cls, "__annotations__", {}):
        cls.created_at = mapped_column(default=lambda: datetime.now(UTC))
        cls.__annotations__ = {**getattr(cls, "__annotations__", {}), "created_at": Mapped[datetime | None]}
    if "updated_at" not in cls.__dict__ and "updated_at" not in getattr(cls, "__annotations__", {}):
        cls.updated_at = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
        cls.__annotations__ = {**cls.__annotations__, "updated_at": Mapped[datetime | None]}


# ---------------------------------------------------------------- mixins (T-31)


class HasUuids:
    """`class Invoice(HasUuids, Model)`: a UUIDv7 primary key instead of the big-integer default."""

    @declared_attr
    def id(cls) -> Mapped[str]:  # noqa: N805
        from sqlalchemy import String

        return mapped_column(String(36), primary_key=True, default=lambda: str(uuid7()))


class HasUlids:
    """`class Invoice(HasUlids, Model)`: a 26-character ULID primary key."""

    @declared_attr
    def id(cls) -> Mapped[str]:  # noqa: N805
        from sqlalchemy import String

        return mapped_column(String(26), primary_key=True, default=ulid)


class SoftDeletes:
    """`class Post(SoftDeletes, Model)`: `delete()` sets `deleted_at` instead of removing the row."""

    __soft_deletes__: ClassVar[bool] = True

    @declared_attr
    def deleted_at(cls) -> Mapped[datetime | None]:  # noqa: N805
        return mapped_column(default=None)

    async def delete(self) -> None:  # type: ignore[override]
        self.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        await self.save()  # type: ignore[attr-defined]

    async def restore(self) -> Self:
        self.deleted_at = None  # type: ignore[attr-defined]
        await self.save()  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    async def force_delete(self) -> None:
        async def _delete(session: Any) -> None:
            await session.delete(self)

        await write(_delete)

    def trashed(self) -> bool:
        return self.deleted_at is not None  # type: ignore[attr-defined]

    @classmethod
    def with_trashed(cls) -> Any:
        return cls.query().with_trashed()  # type: ignore[attr-defined]

    @classmethod
    def only_trashed(cls) -> Any:
        return cls.query().only_trashed()  # type: ignore[attr-defined]


@event.listens_for(Session, "do_orm_execute")
def _filter_soft_deleted(execute_state: Any) -> None:
    """Default scope for `SoftDeletes` models: hide `deleted_at IS NOT NULL` rows (T-31).

    Skipped when the statement's execution options carry `with_trashed`/`only_trashed`, which
    `Builder._final_statement()` always sets (to `False` by default).
    """
    if not execute_state.is_select:
        return
    options = execute_state.execution_options
    if options.get("with_trashed"):
        return
    only_trashed = options.get("only_trashed")
    for mapper in execute_state.all_mappers:
        cls = mapper.class_
        if not getattr(cls, "__soft_deletes__", False):
            continue
        criteria = (
            with_loader_criteria(cls, lambda c: c.deleted_at.is_not(None), include_aliases=True)
            if only_trashed
            else with_loader_criteria(cls, lambda c: c.deleted_at.is_(None), include_aliases=True)
        )
        execute_state.statement = execute_state.statement.options(criteria)


# ---------------------------------------------------------------- query scopes (T-32)


class _Scope:
    """`@scope` descriptor: `Post.published()` starts `Post.query()`; `builder.published()` (via
    `Builder.__getattr__`) continues the chain by calling the raw function directly."""

    def __init__(self, func: Any) -> None:
        self.func = func
        self.__name__ = getattr(func, "__name__", "scope")

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        model = objtype if objtype is not None else type(obj)

        def bound(*args: Any, **kwargs: Any) -> Any:
            return self.func(model, model.query(), *args, **kwargs)

        return bound

    def __call__(self, model: type, query: Any, *args: Any, **kwargs: Any) -> Any:
        return self.func(model, query, *args, **kwargs)


def scope(func: Any) -> _Scope:
    return _Scope(func)
