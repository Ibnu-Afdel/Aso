import asyncio

from aiogram import Bot

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    await bot.set_webhook(settings.telegram_webhook_url)
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
