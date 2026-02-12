from pathlib import Path
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings


def _alembic_heads() -> set[str]:
    backend_root = Path(__file__).resolve().parents[2]
    alembic_ini_path = backend_root / "alembic.ini"
    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    script = ScriptDirectory.from_config(config)
    return set(script.get_heads())


async def _db_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            return None


async def run_startup_checks(settings: Settings, engine: AsyncEngine) -> None:
    if settings.environment.lower() != "production":
        return

    errors: list[str] = []

    if not os.getenv("DATABASE_URL"):
        errors.append("DATABASE_URL is required")
    if settings.bot_enabled and not os.getenv("TELEGRAM_BOT_TOKEN"):
        errors.append("TELEGRAM_BOT_TOKEN is required when BOT_ENABLED=true")
    if settings.fernet_key_required and not os.getenv("FERNET_KEY"):
        errors.append("FERNET_KEY is required when FERNET_KEY_REQUIRED=true")

    db_rev = await _db_revision(engine)
    if db_rev is None:
        errors.append("alembic_version table is missing or unreadable")
    else:
        heads = _alembic_heads()
        if db_rev not in heads:
            errors.append("database revision is not at alembic head")

    if errors:
        for error in errors:
            logger.bind(event_type="startup_check_failed").error(error)
        raise RuntimeError("Startup checks failed")
