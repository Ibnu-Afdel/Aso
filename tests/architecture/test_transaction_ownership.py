import pytest
from sqlalchemy import Integer, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from app.bootstrap.session_manager import SessionManager
from app.services.users import UserAppService


class Base(DeclarativeBase):
    pass


class EntityModel(Base):
    __tablename__ = "test_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)


class EntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> EntityModel | None:
        return await self._session.scalar(
            select(EntityModel).where(EntityModel.telegram_id == telegram_id)
        )

    async def create(self, telegram_id: int) -> EntityModel:
        entity = EntityModel(telegram_id=telegram_id)
        self._session.add(entity)
        await self._session.flush()
        return entity


class EntityModuleService:
    def __init__(self, repo: EntityRepository) -> None:
        self._repo = repo

    async def ensure_user(self, telegram_id: int) -> EntityModel:
        existing = await self._repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            return existing
        return await self._repo.create(telegram_id)


async def _build_test_stack():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    session_manager = SessionManager(session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine, session_manager


def _module_service_factory(session: AsyncSession) -> EntityModuleService:
    return EntityModuleService(EntityRepository(session))


@pytest.mark.asyncio
async def test_repository_create_does_not_persist_without_commit() -> None:
    engine, session_manager = await _build_test_stack()

    async with session_manager.session_scope(commit_on_exit=False):
        session = session_manager.get_session()
        repo = EntityRepository(session)
        await repo.create(telegram_id=10001)

    async with session_manager.session_scope():
        session = session_manager.get_session()
        persisted = await session.scalar(select(EntityModel).where(EntityModel.telegram_id == 10001))
        assert persisted is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_app_service_commit_on_exit_persists_data() -> None:
    engine, session_manager = await _build_test_stack()

    app_service = UserAppService(session_manager, _module_service_factory)
    await app_service.ensure_user(telegram_id=10002)

    async with session_manager.session_scope():
        session = session_manager.get_session()
        persisted = await session.scalar(select(EntityModel).where(EntityModel.telegram_id == 10002))
        assert persisted is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_exception_inside_service_rolls_back() -> None:
    engine, session_manager = await _build_test_stack()

    class ExplodingAppService:
        def __init__(self, sm: SessionManager) -> None:
            self._sm = sm

        async def create_then_fail(self, telegram_id: int) -> None:
            async with self._sm.session_scope(commit_on_exit=True):
                session = self._sm.get_session()
                repo = EntityRepository(session)
                await repo.create(telegram_id=telegram_id)
                raise RuntimeError("boom")

    service = ExplodingAppService(session_manager)
    with pytest.raises(RuntimeError, match="boom"):
        await service.create_then_fail(telegram_id=10003)

    async with session_manager.session_scope():
        session = session_manager.get_session()
        persisted = await session.scalar(select(EntityModel).where(EntityModel.telegram_id == 10003))
        assert persisted is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_nested_commit_request_only_commits_at_outer_scope() -> None:
    engine, session_manager = await _build_test_stack()

    app_service = UserAppService(session_manager, _module_service_factory)

    async with session_manager.session_scope(commit_on_exit=False):
        await app_service.ensure_user(telegram_id=10004)
        session = session_manager.get_session()
        visible_in_tx = await session.scalar(select(EntityModel).where(EntityModel.telegram_id == 10004))
        assert visible_in_tx is not None

    async with session_manager.session_scope():
        session = session_manager.get_session()
        persisted = await session.scalar(select(EntityModel).where(EntityModel.telegram_id == 10004))
        assert persisted is not None

    await engine.dispose()
