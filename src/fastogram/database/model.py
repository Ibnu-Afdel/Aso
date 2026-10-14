"""`Model`: Eloquent-style base class over SQLAlchemy 2.1 (T-31).

SEED (spine): table naming, `id`/timestamps, `find`/`find_or_fail`/`create`/`save`/`delete`/
`all`/`refresh`/`to_dict`, the lazy-load guard. The database package task completes T-31..T-34
(Builder, fillable/hidden, UtcDateTime, relations API, paginators, scopes, soft deletes, ...).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Self

import inflect
from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.strategies import _LazyLoader  # private: pinned sqlalchemy >=2.1.4,<2.2 (S-2)

from fastogram.database.scope import current_scope, write
from fastogram.exceptions.types import LazyLoadingViolation, ModelNotFound

_inflect = inflect.engine()


def table_name_for(class_name: str) -> str:
    """`BlogPost` → `blog_posts` (snake_case plural, like Laravel)."""
    import re

    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    parts = snake.split("_")
    parts[-1] = _inflect.plural_noun(parts[-1]) or parts[-1]
    return "_".join(parts)


@RelationshipProperty.strategy_for(lazy="fastogram")
class _PreventLazyLoader(_LazyLoader):
    """`lazy="raise"` with Laravel's `preventLazyLoading` message (S-2)."""

    def __init__(self, parent: Any, strategy_key: Any) -> None:
        super().__init__(parent, strategy_key)
        self._raise_always = True

    def _invoke_raise_load(self, state: Any, passive: Any, lazy: Any) -> None:
        raise LazyLoadingViolation(state.class_.__name__, self.key)


class Model(DeclarativeBase):
    __abstract__ = True
    __timestamps__: bool = True

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return table_name_for(cls.__name__)

    id: Mapped[int] = mapped_column(primary_key=True)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if not cls.__dict__.get("__abstract__", False) and cls.__dict__.get("__timestamps__", getattr(cls, "__timestamps__", True)):
            if "created_at" not in cls.__dict__ and "created_at" not in getattr(cls, "__annotations__", {}):
                cls.created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=True)
                cls.__annotations__ = {**getattr(cls, "__annotations__", {}), "created_at": Mapped[datetime | None]}
            if "updated_at" not in cls.__dict__ and "updated_at" not in getattr(cls, "__annotations__", {}):
                cls.updated_at = mapped_column(
                    DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=True
                )
                cls.__annotations__ = {**cls.__annotations__, "updated_at": Mapped[datetime | None]}
        super().__init_subclass__(**kwargs)

    # ------------------------------------------------------------ reading

    @classmethod
    async def find(cls, id: Any) -> Self | None:
        return await current_scope().session().get(cls, id)

    @classmethod
    async def find_or_fail(cls, id: Any) -> Self:
        obj = await cls.find(id)
        if obj is None:
            raise ModelNotFound(cls.__name__, [id])
        return obj

    @classmethod
    async def all(cls) -> list[Self]:
        return list((await current_scope().session().scalars(select(cls))).all())

    @classmethod
    async def count(cls) -> int:
        return int(await current_scope().session().scalar(select(func.count()).select_from(cls)) or 0)

    # ------------------------------------------------------------ writing (savepoint + autocommit)

    @classmethod
    async def create(cls, **data: Any) -> Self:
        obj = cls(**data)
        await obj.save()
        return obj

    async def save(self) -> Self:
        await write(lambda session: session.add(self))
        return self

    async def update(self, **data: Any) -> Self:
        for key, value in data.items():
            setattr(self, key, value)
        return await self.save()

    async def delete(self) -> None:
        async def _delete(session: Any) -> None:
            await session.delete(self)

        await write(_delete)

    async def refresh(self) -> Self:
        await current_scope().session().refresh(self)
        return self

    # ------------------------------------------------------------ serialisation

    def to_dict(self) -> dict[str, Any]:
        hidden = set(getattr(self, "__hidden__", ()))
        return {c.key: getattr(self, c.key) for c in self.__table__.columns if c.key not in hidden}

    def only(self, *keys: str) -> dict[str, Any]:
        return {k: getattr(self, k) for k in keys}


def has_many(model: str, **kw: Any) -> Any:
    return relationship(model, lazy="fastogram", **kw)


def belongs_to(model: str, **kw: Any) -> Any:
    return relationship(model, lazy="fastogram", **kw)


def has_one(model: str, **kw: Any) -> Any:
    return relationship(model, lazy="fastogram", uselist=False, **kw)
