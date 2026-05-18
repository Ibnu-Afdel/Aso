import pytest

from app.bootstrap import startup_checks
from app.core.config import Settings


@pytest.mark.asyncio
async def test_missing_database_url_fails_startup(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("BOT_ENABLED", "false")

    async def fake_db_revision(_engine):
        return "head"

    monkeypatch.setattr(startup_checks, "_db_revision", fake_db_revision)
    monkeypatch.setattr(startup_checks, "_alembic_heads", lambda: {"head"})

    settings = Settings(environment="production", bot_enabled=False)
    with pytest.raises(RuntimeError, match="Startup checks failed"):
        await startup_checks.run_startup_checks(settings, engine=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_startup_checks_pass_with_required_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("BOT_ENABLED", "false")

    async def fake_db_revision(_engine):
        return "head"

    monkeypatch.setattr(startup_checks, "_db_revision", fake_db_revision)
    monkeypatch.setattr(startup_checks, "_alembic_heads", lambda: {"head"})

    settings = Settings(environment="production", bot_enabled=False)
    await startup_checks.run_startup_checks(settings, engine=None)  # type: ignore[arg-type]
