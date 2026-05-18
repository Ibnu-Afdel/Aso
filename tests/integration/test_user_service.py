"""Unit tests for UserService (business logic layer)."""

from unittest.mock import AsyncMock

import pytest

from app.modules.users.models import User
from app.modules.users.service import UserService


def _make_repo(existing_user=None):
    repo = AsyncMock()
    repo.get_by_telegram_id.return_value = existing_user
    repo.create.return_value = User(id=1, telegram_id=42)
    return repo


@pytest.mark.asyncio
async def test_ensure_user_creates_when_missing():
    repo = _make_repo(existing_user=None)
    svc = UserService(repo)
    user = await svc.ensure_user(telegram_id=42)
    repo.create.assert_awaited_once_with(telegram_id=42)
    assert user.telegram_id == 42


@pytest.mark.asyncio
async def test_ensure_user_returns_existing():
    existing = User(id=7, telegram_id=99)
    repo = _make_repo(existing_user=existing)
    svc = UserService(repo)
    user = await svc.ensure_user(telegram_id=99)
    repo.create.assert_not_awaited()
    assert user.id == 7
