"""Shared async DB fixtures for integration tests."""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # SQLite only enables autoincrement for `INTEGER PRIMARY KEY`, not `BIGINT NOT NULL
    # PRIMARY KEY (id)` which is what SQLAlchemy emits for BigInteger columns. Using raw
    # DDL here keeps the test schema functionally equivalent without touching the model.
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (telegram_id)
            )
        """))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
