"""S-2 spike: request-scoped AsyncSession via contextvars, savepoint writes, test binding.

Throwaway code. It is the shape the real `fastogram.database` core will take.
"""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Self

from sqlalchemy import exc as sa_exc, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class LazyLoadingViolation(RuntimeError):
    pass


class _Engine:
    engine: AsyncEngine | None = None
    maker: async_sessionmaker[AsyncSession] | None = None


def configure(engine: AsyncEngine) -> None:
    if engine.dialect.name == "sqlite":
        _sqlite_transactions(engine)
    _Engine.engine = engine
    _Engine.maker = async_sessionmaker(engine, expire_on_commit=False)


def _sqlite_transactions(engine: AsyncEngine) -> None:
    """pysqlite/aiosqlite do not emit BEGIN themselves, so SAVEPOINT/RELEASE would commit.
    SQLAlchemy's documented recipe: take over transaction control."""
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _connect(dbapi_connection, record):  # type: ignore[no-untyped-def]
        dbapi_connection.isolation_level = None
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _begin(conn):  # type: ignore[no-untyped-def]
        conn.exec_driver_sql("BEGIN")


_scope: contextvars.ContextVar["Scope | None"] = contextvars.ContextVar("fastogram_db_scope", default=None)
_test_binding: contextvars.ContextVar[AsyncConnection | None] = contextvars.ContextVar(
    "fastogram_db_test_binding", default=None
)


class Scope:
    def __init__(self) -> None:
        self._session: AsyncSession | None = None
        self.depth = 0
        self.after_commit: list[Callable[[], Any]] = []

    def session(self) -> AsyncSession:
        if self._session is None:
            conn = _test_binding.get()
            if conn is not None:
                self._session = AsyncSession(
                    bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
                )
            else:
                assert _Engine.maker is not None, "database not configured"
                self._session = _Engine.maker()
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.rollback()
            await self._session.close()
            self._session = None


def current_scope() -> Scope:
    scope = _scope.get()
    if scope is None:
        raise RuntimeError("No database scope. Use `async with DB.scope():`.")
    return scope


class DB:
    @staticmethod
    @asynccontextmanager
    async def scope(fresh: bool = False) -> AsyncIterator[Scope]:
        existing = _scope.get()
        if existing is not None and not fresh:
            yield existing
            return
        scope = Scope()
        token = _scope.set(scope)
        try:
            yield scope
        finally:
            await scope.close()
            _scope.reset(token)

    @staticmethod
    def session() -> AsyncSession:
        return current_scope().session()

    @staticmethod
    @asynccontextmanager
    async def transaction() -> AsyncIterator[None]:
        scope = current_scope()
        session = scope.session()
        scope.depth += 1
        outermost = scope.depth == 1
        nested = await session.begin_nested()
        try:
            yield
        except BaseException:
            await nested.rollback()
            scope.depth -= 1
            if outermost:
                scope.after_commit.clear()
                await session.commit()  # end the surrounding (read-only) transaction, no full rollback
            raise
        else:
            await nested.commit()
            scope.depth -= 1
            if outermost:
                await session.commit()
                callbacks, scope.after_commit = scope.after_commit, []
                for cb in callbacks:
                    result = cb()
                    if hasattr(result, "__await__"):
                        await result

    @staticmethod
    def after_commit(cb: Callable[[], Any]) -> None:
        current_scope().after_commit.append(cb)


# ---------------------------------------------------------------- Model


class Model(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)

    @classmethod
    async def find(cls, id: Any) -> Self | None:
        return await DB.session().get(cls, id)

    @classmethod
    async def create(cls, **data: Any) -> Self:
        obj = cls(**data)
        await obj.save()
        return obj

    async def save(self) -> Self:
        scope = current_scope()
        session = scope.session()
        async with session.begin_nested():
            session.add(self)
            await session.flush()
        if scope.depth == 0:
            await session.commit()
        return self

    async def delete(self) -> None:
        scope = current_scope()
        session = scope.session()
        async with session.begin_nested():
            await session.delete(self)
            await session.flush()
        if scope.depth == 0:
            await session.commit()

    async def refresh(self) -> Self:
        await DB.session().refresh(self)
        return self

    @classmethod
    async def all(cls) -> list[Self]:
        return list((await DB.session().scalars(select(cls))).all())


from sqlalchemy.orm.relationships import RelationshipProperty  # noqa: E402
from sqlalchemy.orm.strategies import _LazyLoader  # noqa: E402  (private; pinned SQLAlchemy 2.1)


@RelationshipProperty.strategy_for(lazy="fastogram")
class _PreventLazyLoader(_LazyLoader):
    """lazy='raise' with a Laravel-style message (Model::preventLazyLoading)."""

    def __init__(self, parent: Any, strategy_key: Any) -> None:
        super().__init__(parent, strategy_key)
        self._raise_always = True

    def _invoke_raise_load(self, state: Any, passive: Any, lazy: Any) -> None:
        cls, name = state.class_.__name__, self.key
        raise LazyLoadingViolation(
            f"Attempted to lazy load [{name}] on model [{cls}]. "
            f'Eager load it: {cls}.with_("{name}") or `await model.load("{name}")`.'
        )


def has_many(target: str, **kw: Any) -> Any:
    return relationship(target, lazy="fastogram", **kw)


def belongs_to(target: str, **kw: Any) -> Any:
    return relationship(target, lazy="fastogram", **kw)
