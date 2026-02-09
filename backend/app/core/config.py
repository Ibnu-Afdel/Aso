from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "telegram-fastapi-template"
    environment: str = "production"
    debug: bool = False
    api_prefix: str = "/api"

    bot_enabled: bool = True
    telegram_bot_token: str | None = None
    telegram_webhook_url: str | None = None

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
    redis_url: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def _validate_bot_settings(self) -> "Settings":
        if self.bot_enabled:
            missing = []
            if not self.telegram_bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not self.telegram_webhook_url:
                missing.append("TELEGRAM_WEBHOOK_URL")
            if missing:
                raise ValueError(
                    "BOT_ENABLED=true requires: " + ", ".join(missing)
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
