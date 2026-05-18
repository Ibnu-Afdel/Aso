from contextlib import asynccontextmanager

import pytest

import app.core.db as db
import app.services.users as users_service_module
from app.services.users import UserAppService


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _FakeSessionMaker:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    @asynccontextmanager
    async def __call__(self):
        yield self._session


@pytest.mark.asyncio
async def test_session_scope_without_commit_does_not_commit(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(db, "async_session_maker", _FakeSessionMaker(session))

    async with db.session_scope(commit_on_exit=False):
        pass

    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_session_scope_commit_on_exit_commits(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(db, "async_session_maker", _FakeSessionMaker(session))

    async with db.session_scope(commit_on_exit=True):
        pass

    assert session.commits == 1
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_session_scope_rolls_back_on_exception(monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(db, "async_session_maker", _FakeSessionMaker(session))

    with pytest.raises(RuntimeError, match="boom"):
        async with db.session_scope(commit_on_exit=True):
            raise RuntimeError("boom")

    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_user_app_service_ensure_user_uses_session_scope(monkeypatch) -> None:
    in_scope = False
    seen_ids: list[int] = []

    class FakeRepo:
        def __init__(self, session) -> None:
            assert in_scope is True
            self._session = session

    class FakeModuleService:
        def __init__(self, repo: FakeRepo) -> None:
            self._repo = repo

        async def ensure_user(self, telegram_id: int):
            assert in_scope is True
            seen_ids.append(telegram_id)
            return {"telegram_id": telegram_id}

    @asynccontextmanager
    async def fake_session_scope(commit_on_exit: bool = False):
        nonlocal in_scope
        assert commit_on_exit is True
        in_scope = True
        try:
            yield object()
        finally:
            in_scope = False

    monkeypatch.setattr(users_service_module, "session_scope", fake_session_scope)
    monkeypatch.setattr(users_service_module, "UserRepository", FakeRepo)
    monkeypatch.setattr(users_service_module, "UserService", FakeModuleService)

    app_service = UserAppService()
    result = await app_service.ensure_user(telegram_id=123)

    assert result == {"telegram_id": 123}
    assert seen_ids == [123]
