"""Database test assertions (T-57): `assert_database_has/missing/count`, `assert_model_exists/missing`.

Each assertion runs a fresh `AsyncSession` bound to whatever connection the current test's
scope is using (the S-2 test-binding connection when a `db` fixture is open, or the real engine
otherwise), never the scope's own session -- so they never see a stale identity map, and always
see uncommitted data written through the test's own savepoints (T-57 "How it works" #7).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

__all__ = [
    "assert_database_count",
    "assert_database_has",
    "assert_database_missing",
    "assert_model_exists",
    "assert_model_missing",
]


async def _fresh_session() -> AsyncSession:
    from fastogram.database.scope import current_scope

    bind = current_scope().session().bind
    if isinstance(bind, AsyncConnection):
        return AsyncSession(bind=bind, join_transaction_mode="create_savepoint")
    return AsyncSession(bind=bind)


def _where_clause(attributes: dict[str, Any]) -> str:
    if not attributes:
        return "1 = 1"
    return " AND ".join(f"{column} = :{column}" for column in attributes)


async def _exists(table: str, attributes: dict[str, Any]) -> bool:
    session = await _fresh_session()
    try:
        sql = text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {_where_clause(attributes)})")
        result = await session.execute(sql, attributes)
        return bool(result.scalar())
    finally:
        await session.close()


async def assert_database_has(table: str, attributes: dict[str, Any]) -> None:
    """`await assert_database_has("posts", {"title": "Hi", "user_id": user.id})`."""
    found = await _exists(table, attributes)
    assert found, f"Failed asserting that a row exists in [{table}] matching {attributes!r}."


async def assert_database_missing(table: str, attributes: dict[str, Any]) -> None:
    found = await _exists(table, attributes)
    assert not found, f"Failed asserting that no row exists in [{table}] matching {attributes!r} (one was found)."


async def assert_database_count(table: str, count: int) -> None:
    session = await _fresh_session()
    try:
        result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        actual = int(result.scalar() or 0)
    finally:
        await session.close()
    assert actual == count, f"Failed asserting that [{table}] has {count} row(s); found {actual}."


def _model_identity(model: Any) -> tuple[str, dict[str, Any]]:
    mapper = sa_inspect(type(model)).mapper
    table = mapper.local_table.name
    attributes: dict[str, Any] = {}
    for column in mapper.primary_key:
        prop = mapper.get_property_by_column(column)
        attributes[column.name] = getattr(model, prop.key)
    return table, attributes


async def assert_model_exists(model: Any) -> None:
    """`await assert_model_exists(post)`: the model's table and primary key still exist."""
    table, attributes = _model_identity(model)
    await assert_database_has(table, attributes)


async def assert_model_missing(model: Any) -> None:
    table, attributes = _model_identity(model)
    await assert_database_missing(table, attributes)
