from app.bootstrap.logging import configure_logging
from app.core.config import get_settings
from app.services.health import HealthAppService
from app.services.telegram_webhook import TelegramWebhookAppService
from app.services.users import UserAppService

_user_app_service: UserAppService | None = None
_health_app_service: HealthAppService | None = None
_telegram_webhook_app_service: TelegramWebhookAppService | None = None
_logging_initialized = False


def get_user_app_service() -> UserAppService:
    global _user_app_service
    if _user_app_service is None:
        _user_app_service = UserAppService()
    return _user_app_service


def get_health_app_service() -> HealthAppService:
    global _health_app_service
    if _health_app_service is None:
        _health_app_service = HealthAppService()
    return _health_app_service


def get_telegram_webhook_app_service() -> TelegramWebhookAppService:
    global _telegram_webhook_app_service
    if _telegram_webhook_app_service is None:
        _telegram_webhook_app_service = TelegramWebhookAppService()
    return _telegram_webhook_app_service


def initialize_logging() -> None:
    global _logging_initialized
    if _logging_initialized:
        return
    configure_logging(get_settings())
    _logging_initialized = True
