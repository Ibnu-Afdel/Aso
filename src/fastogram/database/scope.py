"""The unit of work: one `AsyncSession` per request / job / command / test (T-30, S-2).

Writes run inside SAVEPOINTs (`begin_nested`) at every level, so a failed write never forces a
full rollback that would expire every loaded object (D-005).
"""

from __future__ import annotations

import contextvars
import inspect
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

_scope: contextvars.ContextVar[Scope | None] = contextvars.ContextVar("fastogram_db_scope", default=None)
_test_binding: contextvars.ContextVar[AsyncConnection | None] = contextvars.ContextVar(
    "fastogram_db_test_binding", default=None
)


class Scope:
    def __init__(self) -> None:
        self._session: AsyncSession | None = None
        self.depth = 0
        self.after_commit_callbacks: list[Callable[[], Any]] = []

    def session(self) -> AsyncSession:
        if self._session is None:
            connection = _test_binding.get()
            if connection is not None:
                self._session = AsyncSession(
                    bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
                )
            else:
                from fastogram.database.engine import session_maker

                self._session = session_maker()()
        return self._session

    @property
    def has_session(self) -> bool:
        return self._session is not None

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.rollback()
            finally:
                await self._session.close()
                self._session = None


def current_scope() -> Scope:
    scope = _scope.get()
    if scope is None:
        raise RuntimeError(
            "No database scope is open. Models work inside requests, jobs, commands and tests; "
            "elsewhere use `async with DB.scope():`."
        )
    return scope


def set_test_binding(connection: AsyncConnection | None) -> contextvars.Token[AsyncConnection | None]:
    return _test_binding.set(connection)


def reset_test_binding(token: contextvars.Token[AsyncConnection | None]) -> None:
    _test_binding.reset(token)


@asynccontextmanager
async def open_scope(fresh: bool = False) -> AsyncIterator[Scope]:
    existing = _scope.get()
    if existing is not None and not fresh:
        yield existing
        return
    scope = Scope()
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        try:
            await scope.close()
        finally:
            _scope.reset(token)


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
        if nested.is_active:
            await nested.rollback()
        scope.depth -= 1
        if outermost:
            scope.after_commit_callbacks.clear()
            await session.commit()  # end the surrounding read transaction without a full rollback
        raise
    else:
        await nested.commit()
        scope.depth -= 1
        if outermost:
            await session.commit()
            callbacks, scope.after_commit_callbacks = scope.after_commit_callbacks, []
            for callback in callbacks:
                result = callback()
                if inspect.isawaitable(result):
                    await result


async def write(fn: Callable[[AsyncSession], Any]) -> Any:
    """Run one write inside a savepoint; autocommit when no transaction is open."""
    scope = current_scope()
    session = scope.session()
    async with session.begin_nested():
        result = fn(session)
        if inspect.isawaitable(result):
            result = await result
        await session.flush()
    if scope.depth == 0:
        await session.commit()
    return result
