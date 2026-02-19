"""Middleware that injects app services into handler context for aiogram DI."""

from aiogram import BaseMiddleware

from app.bootstrap.container import get_user_app_service


class ServiceInjectionMiddleware(BaseMiddleware):
    """Inject app services into data so handlers receive them as parameters."""

    async def __call__(self, handler, event, data):
        data["user_app_service"] = get_user_app_service()
        return await handler(event, data)
