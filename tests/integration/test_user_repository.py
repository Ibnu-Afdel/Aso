"""Integration tests for UserRepository against a real (SQLite) database."""

import pytest

from app.modules.users.repository import UserRepository


@pytest.mark.asyncio
async def test_create_user(db_session):
    repo = UserRepository(db_session)
    user = await repo.create(telegram_id=111)
    assert user.id is not None
    assert user.telegram_id == 111
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_get_by_telegram_id_found(db_session):
    repo = UserRepository(db_session)
    await repo.create(telegram_id=222)
    user = await repo.get_by_telegram_id(222)
    assert user is not None
    assert user.telegram_id == 222


@pytest.mark.asyncio
async def test_get_by_telegram_id_not_found(db_session):
    repo = UserRepository(db_session)
    user = await repo.get_by_telegram_id(999)
    assert user is None


@pytest.mark.asyncio
async def test_create_is_idempotent_via_get(db_session):
    repo = UserRepository(db_session)
    first = await repo.create(telegram_id=333)
    found = await repo.get_by_telegram_id(333)
    assert found is not None
    assert found.id == first.id
