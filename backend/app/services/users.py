from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.session_manager import SessionManager
from app.modules.users.service import UserService


class UserAppService:
    def __init__(
        self,
        session_manager: SessionManager,
        module_service_factory: Callable[[AsyncSession], UserService],
    ) -> None:
        self._session_manager = session_manager
        self._module_service_factory = module_service_factory

    async def ensure_user(self, telegram_id: int):
        async with self._session_manager.session_scope(commit_on_exit=True):
            session = self._session_manager.get_session()
        service = self._module_service_factory(session)
        return await service.ensure_user(telegram_id=telegram_id)
