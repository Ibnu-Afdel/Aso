"""Inject app services into handler context for aiogram DI.

To add a new service: (1) add data['<service_key>'] = get_<name>_app_service() here,
(2) add <service_key>: <ServiceType> param to handlers that need it.
"""

from aiogram import BaseMiddleware

from app.bootstrap.container import get_user_app_service


class ServiceInjectionMiddleware(BaseMiddleware):
    """Adds app services to data dict. Handlers receive them as keyword params."""

    async def __call__(self, handler, event, data):
        data["user_app_service"] = get_user_app_service()
        return await handler(event, data)
