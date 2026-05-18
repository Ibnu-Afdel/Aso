from aiogram import BaseMiddleware
from loguru import logger

from app.bootstrap.request_context import get_request_id


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception:
            user_id = None
            from_user = getattr(event, "from_user", None)
            if from_user is not None:
                user_id = getattr(from_user, "id", None)
            logger.bind(
                request_id=get_request_id(),
                event_type="bot_handler_exception",
                user_id=user_id,
            ).exception("Unhandled bot handler exception")
            raise
