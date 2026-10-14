"""`DB`: scopes, transactions, raw SQL, and the query listener (T-30)."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fastogram.database import scope as _scope

__all__ = ["DB", "QueryExecuted"]


@dataclass(frozen=True)
class QueryExecuted:
    """Passed to every `DB.listen()` callback (T-30)."""

    sql: str
    bindings: dict[str, Any]
    time_ms: float
    connection_name: str | None = None


_listeners: list[Callable[[QueryExecuted], Any]] = []


def notify(event: QueryExecuted) -> None:
    for listener in _listeners:
        listener(event)


class DB:
    """`DB.scope()`, `DB.transaction()`, raw SQL helpers, `DB.listen()` (T-30)."""

    @staticmethod
    def scope(fresh: bool = False) -> Any:
        return _scope.open_scope(fresh=fresh)

    @staticmethod
    def transaction(fn: Callable[[], Any] | None = None, *, attempts: int = 1) -> Any:
        return _scope.transaction(fn, attempts=attempts)

    @staticmethod
    def after_commit(callback: Callable[[], Any]) -> None:
        scope = _scope.current_scope()
        if scope.depth == 0:
            # Not inside a transaction: Laravel runs it immediately.
            result = callback()
            if inspect.isawaitable(result):
                import asyncio

                asyncio.ensure_future(result)
            return
        scope.after_commit_callbacks.append(callback)

    @staticmethod
    def session() -> AsyncSession:
        return _scope.current_scope().session()

    @staticmethod
    def listen(callback: Callable[[QueryExecuted], Any]) -> None:
        _listeners.append(callback)

    # ------------------------------------------------------------ raw SQL (named bindings only)

    @staticmethod
    async def select(sql: str, bindings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = await DB.session().execute(text(sql), bindings or {})
        return [dict(row._mapping) for row in result]

    @staticmethod
    async def select_one(sql: str, bindings: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = await DB.select(sql, bindings)
        return rows[0] if rows else None

    @staticmethod
    async def scalar(sql: str, bindings: dict[str, Any] | None = None) -> Any:
        return await DB.session().scalar(text(sql), bindings or {})

    @staticmethod
    async def insert(sql: str, bindings: dict[str, Any] | None = None) -> bool:
        async def run(session: AsyncSession) -> bool:
            await session.execute(text(sql), bindings or {})
            return True

        return await _scope.write(run)

    @staticmethod
    async def update(sql: str, bindings: dict[str, Any] | None = None) -> int:
        async def run(session: AsyncSession) -> int:
            result = await session.execute(text(sql), bindings or {})
            return int(result.rowcount)  # type: ignore[attr-defined]

        return await _scope.write(run)

    @staticmethod
    async def delete(sql: str, bindings: dict[str, Any] | None = None) -> int:
        return await DB.update(sql, bindings)

    @staticmethod
    async def statement(sql: str, bindings: dict[str, Any] | None = None) -> bool:
        async def run(session: AsyncSession) -> bool:
            await session.execute(text(sql), bindings or {})
            return True

        return await _scope.write(run)
