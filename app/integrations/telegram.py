import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher

from app.core.config import get_settings

settings = get_settings()


async def setup_telegram(bot: Bot, dp: Dispatcher) -> asyncio.Task | None:
    if settings.telegram_delivery_mode == "polling":
        await bot.delete_webhook(drop_pending_updates=False)
        return asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    await bot.set_webhook(
        settings.telegram_webhook_url,
        secret_token=settings.telegram_webhook_secret or None,
    )
    return None


async def teardown_telegram(bot: Bot, polling_task: asyncio.Task | None) -> None:
    if polling_task is not None:
        polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await polling_task
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()
