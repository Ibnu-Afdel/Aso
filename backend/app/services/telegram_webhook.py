import logging

from aiogram import Dispatcher, types
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class TelegramWebhookAppService:
    async def handle_request(
        self,
        payload: dict,
        *,
        bot_enabled: bool,
        dispatcher: Dispatcher | None,
    ) -> JSONResponse | dict[str, bool]:
        if not bot_enabled or dispatcher is None:
            return JSONResponse(
                status_code=503,
                content={"error": "telegram_bot_disabled"},
            )

        try:
            update = types.Update.model_validate(payload)
            await dispatcher.feed_webhook_update(dispatcher.bot, update)
        except Exception as exc:  # noqa: BLE001
            logger.exception("telegram webhook processing failed")
            return JSONResponse(status_code=500, content={"error": str(exc)})

        return {"ok": True}
