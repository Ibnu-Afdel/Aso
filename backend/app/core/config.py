from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "telegram-fastapi-template"
    environment: str = "production"
    debug: bool = False
    api_prefix: str = "/api"

    telegram_bot_token: str
    telegram_webhook_url: str

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
    redis_url: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
