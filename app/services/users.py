from app.core.db import session_scope
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


class UserAppService:
    async def ensure_user(self, telegram_id: int):
        async with session_scope(commit_on_exit=True) as session:
            repo = UserRepository(session)
            service = UserService(repo)
            return await service.ensure_user(telegram_id=telegram_id)
