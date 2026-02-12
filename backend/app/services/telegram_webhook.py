from aiogram import Dispatcher, types
from fastapi.responses import JSONResponse
from loguru import logger

from app.bootstrap.request_context import get_request_id
from app.bootstrap.session_manager import SessionManager


class TelegramWebhookAppService:
    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    async def handle_request(
        self,
        payload: dict,
        *,
        bot_enabled: bool,
        dispatcher: Dispatcher | None,
    ) -> JSONResponse | dict[str, bool]:
        async with self._session_manager.session_scope(commit_on_exit=True):
            if not bot_enabled or dispatcher is None:
                return JSONResponse(
                    status_code=503,
                    content={"error": "telegram_bot_disabled"},
                )

            try:
                update = types.Update.model_validate(payload)
                await dispatcher.feed_webhook_update(dispatcher.bot, update)
            except Exception as exc:  # noqa: BLE001
                logger.bind(
                    request_id=get_request_id(),
                    event_type="telegram_webhook_error",
                ).exception("telegram webhook processing failed")
                return JSONResponse(status_code=500, content={"error": str(exc)})

            return {"ok": True}
