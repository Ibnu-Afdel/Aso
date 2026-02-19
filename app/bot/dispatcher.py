from aiogram import Bot, Dispatcher

from app.bot.handlers.start import router as start_router
from app.bot.middlewares import (
    ErrorLoggingMiddleware,
    RateLimitMiddleware,
    ServiceInjectionMiddleware,
)
from app.bot.middlewares.rate_limit_backends import InMemoryBackend, RedisBackend
from app.core.config import get_settings

settings = get_settings()


def _get_rate_limit_backend():
    if settings.rate_limit_backend == "redis":
        return RedisBackend(settings.redis_url)
    return InMemoryBackend()


def get_dispatcher() -> Dispatcher:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.update.middleware(ServiceInjectionMiddleware())
    dp.update.middleware(ErrorLoggingMiddleware())
    dp.update.middleware(
        RateLimitMiddleware(
            backend=_get_rate_limit_backend(),
            limit_per_minute=settings.rate_limit_per_minute,
        )
    )
    dp.include_router(start_router)
    dp.bot = bot  # type: ignore[attr-defined]
    return dp
