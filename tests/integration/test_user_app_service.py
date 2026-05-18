"""Integration tests for UserAppService (session owner layer)."""

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.users import UserAppService


@pytest.mark.asyncio
async def test_ensure_user_creates_new(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    with patch("app.core.db.async_session_maker", factory):
        svc = UserAppService()
        user = await svc.ensure_user(telegram_id=12345)
    assert user.id is not None
    assert user.telegram_id == 12345


@pytest.mark.asyncio
async def test_ensure_user_idempotent(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    with patch("app.core.db.async_session_maker", factory):
        svc = UserAppService()
        first = await svc.ensure_user(telegram_id=99999)
        second = await svc.ensure_user(telegram_id=99999)
    assert first.id == second.id
