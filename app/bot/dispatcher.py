from aiogram import Bot, Dispatcher

from app.bot.handlers.start import router as start_router
from app.bot.middlewares import (
    ErrorLoggingMiddleware,
    RateLimitMiddleware,
    ServiceInjectionMiddleware,
)
from app.core.config import get_settings

settings = get_settings()


def get_dispatcher() -> Dispatcher:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.update.middleware(ServiceInjectionMiddleware())
    dp.update.middleware(ErrorLoggingMiddleware())
    dp.update.middleware(RateLimitMiddleware())
    dp.include_router(start_router)
    dp.bot = bot  # type: ignore[attr-defined]
    return dp
