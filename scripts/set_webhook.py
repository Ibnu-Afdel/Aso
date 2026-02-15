import asyncio
import argparse

from aiogram import Bot

from app.core.config import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set or delete Telegram webhook.")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete webhook instead of setting it.",
    )
    parser.add_argument(
        "--drop-pending-updates",
        action="store_true",
        help="Drop pending updates when deleting webhook.",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    try:
        if args.delete:
            await bot.delete_webhook(drop_pending_updates=args.drop_pending_updates)
            print(
                "Webhook deleted"
                + (" (pending updates dropped)." if args.drop_pending_updates else ".")
            )
            return

        await bot.set_webhook(settings.telegram_webhook_url)
        print(f"Webhook set to {settings.telegram_webhook_url}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
