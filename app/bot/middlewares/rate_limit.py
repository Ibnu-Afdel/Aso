import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit_per_minute: int = 30):
        self.limit = limit_per_minute
        self._buckets = {}

    async def __call__(self, handler, event, data):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            bucket = int(time.time() // 60)
            key = (user_id, bucket)
            count = self._buckets.get(key, 0) + 1
            self._buckets[key] = count
            if count > self.limit:
                return

        return await handler(event, data)
