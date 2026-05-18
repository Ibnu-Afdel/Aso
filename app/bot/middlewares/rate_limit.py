from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.bot.middlewares.rate_limit_backends import RateLimitBackend


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        backend: RateLimitBackend,
        limit_per_minute: int = 30,
    ) -> None:
        self._backend = backend
        self._limit = limit_per_minute

    async def __call__(self, handler, event, data):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is not None:
            if not await self._backend.is_allowed(user_id, self._limit):
                return

        return await handler(event, data)
