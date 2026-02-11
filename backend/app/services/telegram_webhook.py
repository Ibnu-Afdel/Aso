from aiogram import Dispatcher, types


class TelegramWebhookAppService:
    async def handle_update(self, dispatcher: Dispatcher, payload: dict) -> None:
        update = types.Update.model_validate(payload)
        await dispatcher.feed_webhook_update(dispatcher.bot, update)
