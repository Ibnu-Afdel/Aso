from app.modules.users.repository import UserRepository


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def ensure_user(self, telegram_id: int):
        user = await self._repo.get_by_telegram_id(telegram_id)
        if user:
            return user
        return await self._repo.create(telegram_id=telegram_id)
