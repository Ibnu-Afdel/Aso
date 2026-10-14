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
async def _transaction_once() -> AsyncIterator[None]:
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


_RETRYABLE_SQLSTATES = {"40001", "40P01"}  # serialization_failure, deadlock_detected (PostgreSQL)


def _is_retryable(exc: BaseException) -> bool:
    """Deadlock or serialization failure (T-30 `DB.transaction(attempts=)`)."""
    from sqlalchemy.exc import OperationalError

    if not isinstance(exc, OperationalError):
        return False
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in _RETRYABLE_SQLSTATES:
        return True
    return "deadlock" in str(orig or exc).lower() or "database is locked" in str(orig or exc).lower()


def transaction(fn: Callable[[], Any] | None = None, *, attempts: int = 1) -> Any:
    """`async with DB.transaction():` (single attempt) or `await DB.transaction(fn, attempts=3)`.

    A plain `async with` block cannot be re-run from the outside once it has raised (Python gives
    a context manager no way to replay the caller's `with`-suite), so a real "retry the whole
    block" only works for the **callback** form: each attempt opens a fresh savepoint and calls
    `fn()` again from scratch. `attempts=` on the context-manager form is accepted for symmetry
    with Laravel's signature but only ever makes one attempt; see the build report.
    """
    if fn is None:
        return _transaction_once()
    return _retrying_transaction(fn, attempts)


async def _retrying_transaction(fn: Callable[[], Any], attempts: int) -> Any:
    last_exc: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            async with _transaction_once():
                result = fn()
                return await result if inspect.isawaitable(result) else result
        except BaseException as exc:  # noqa: BLE001 - re-raised below when not retryable/out of attempts
            last_exc = exc
            if attempt >= attempts or not _is_retryable(exc):
                raise
    raise last_exc  # pragma: no cover - unreachable (loop always returns or raises)


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
