from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import async_session_maker
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


class UserAppService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_user(self, telegram_id: int):
        async with self._session_factory() as session:
            repo = UserRepository(session)
            service = UserService(repo)
            return await service.ensure_user(telegram_id=telegram_id)


user_app_service = UserAppService(async_session_maker)
