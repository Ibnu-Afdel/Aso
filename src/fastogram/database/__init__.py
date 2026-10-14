"""Database (T-30..T-36)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from fastogram.database import scope as _scope
from fastogram.database.model import Model, belongs_to, has_many, has_one
from fastogram.exceptions.types import LazyLoadingViolation, MassAssignmentError, ModelNotFound, MultipleRecordsFound

__all__ = [
    "DB",
    "LazyLoadingViolation",
    "Mapped",
    "MassAssignmentError",
    "Model",
    "ModelNotFound",
    "MultipleRecordsFound",
    "belongs_to",
    "has_many",
    "has_one",
    "mapped_column",
]


class DB:
    """`DB.transaction()`, `DB.scope()`, raw SQL helpers (T-30). SEED (spine)."""

    @staticmethod
    def scope(fresh: bool = False) -> Any:
        return _scope.open_scope(fresh=fresh)

    @staticmethod
    def transaction() -> Any:
        return _scope.transaction()

    @staticmethod
    def after_commit(callback: Callable[[], Any]) -> None:
        current = _scope.current_scope()
        if current.depth == 0:
            # not in a transaction: run now (Laravel runs immediately outside transactions)
            result = callback()
            if hasattr(result, "__await__"):
                import asyncio

                asyncio.ensure_future(result)
            return
        current.after_commit_callbacks.append(callback)

    @staticmethod
    def session() -> AsyncSession:
        return _scope.current_scope().session()

    @staticmethod
    async def select(sql: str, bindings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = await DB.session().execute(text(sql), bindings or {})
        return [dict(row._mapping) for row in result]

    @staticmethod
    async def scalar(sql: str, bindings: dict[str, Any] | None = None) -> Any:
        return await DB.session().scalar(text(sql), bindings or {})

    @staticmethod
    async def statement(sql: str, bindings: dict[str, Any] | None = None) -> int:
        async def run(session: AsyncSession) -> int:
            result = await session.execute(text(sql), bindings or {})
            return result.rowcount  # type: ignore[attr-defined]

        return await _scope.write(run)


@asynccontextmanager
async def _noop() -> AsyncIterator[None]:  # pragma: no cover
    yield
