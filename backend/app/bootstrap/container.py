from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.bootstrap.session_manager import SessionManager
from app.services.health import HealthAppService
from app.services.telegram_webhook import TelegramWebhookAppService
from app.services.users import UserAppService

_user_app_service: UserAppService | None = None
_health_app_service: HealthAppService | None = None
_telegram_webhook_app_service: TelegramWebhookAppService | None = None
_session_manager: SessionManager | None = None


def _build_user_module_service(session: AsyncSession) -> UserService:
    repo = UserRepository(session)
    return UserService(repo)


def get_user_app_service() -> UserAppService:
    global _user_app_service
    if _user_app_service is None:
        _user_app_service = UserAppService(
            get_session_manager(),
            async_session_maker,
            _build_user_module_service,
        )
    return _user_app_service


def get_health_app_service() -> HealthAppService:
    global _health_app_service
    if _health_app_service is None:
        _health_app_service = HealthAppService()
    return _health_app_service


def get_telegram_webhook_app_service() -> TelegramWebhookAppService:
    global _telegram_webhook_app_service
    if _telegram_webhook_app_service is None:
        _telegram_webhook_app_service = TelegramWebhookAppService(get_session_manager())
    return _telegram_webhook_app_service


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(async_session_maker)
    return _session_manager
