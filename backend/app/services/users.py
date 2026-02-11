from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bootstrap.session_manager import SessionManager
from app.modules.users.service import UserService


class UserAppService:
    def __init__(
        self,
        session_manager: SessionManager,
        session_factory: async_sessionmaker[AsyncSession],
        module_service_factory: Callable[[AsyncSession], UserService],
    ) -> None:
        self._session_manager = session_manager
        self._session_factory = session_factory
        self._module_service_factory = module_service_factory

    async def ensure_user(self, telegram_id: int):
        try:
            session = self._session_manager.get_session()
        except RuntimeError:
            async with self._session_factory() as managed_session:
                service = self._module_service_factory(managed_session)
                return await service.ensure_user(telegram_id=telegram_id)
        service = self._module_service_factory(session)
        return await service.ensure_user(telegram_id=telegram_id)
