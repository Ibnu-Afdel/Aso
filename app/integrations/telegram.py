from aiogram import Bot, Dispatcher

from app.core.config import get_settings

settings = get_settings()


async def setup_telegram_webhook(dp: Dispatcher) -> None:
    bot: Bot = dp.bot
    await bot.set_webhook(settings.telegram_webhook_url)


async def teardown_telegram_webhook(dp: Dispatcher) -> None:
    bot: Bot = dp.bot
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
