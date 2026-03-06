from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "telegram-fastapi-template"
    environment: str = "production"
    debug: bool = False
    api_prefix: str = "/api"

    bot_enabled: bool = True
    telegram_delivery_mode: Literal["polling", "webhook"] = "polling"
    telegram_bot_token: str | None = None
    telegram_webhook_url: str | None = None
    telegram_webhook_secret: str | None = None

    database_url: str = "postgresql+asyncpg://fastapi:password@db:5432/fastapi"
    redis_url: str = "redis://redis:6379/0"
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_limit_per_minute: int = 30
    fernet_key: str | None = None
    fernet_key_required: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def _validate_bot_settings(self) -> "Settings":
        if self.bot_enabled:
            missing = []
            if not self.telegram_bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if (
                self.telegram_delivery_mode == "webhook"
                and not self.telegram_webhook_url
            ):
                missing.append("TELEGRAM_WEBHOOK_URL")
            if missing:
                raise ValueError("BOT_ENABLED=true requires: " + ", ".join(missing))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
