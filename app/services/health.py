from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class HealthAppService:
    def __init__(self, engine: AsyncEngine | None = None) -> None:
        if engine is None:
            from app.core.db import engine as _engine

            engine = _engine
        self._engine = engine

    async def liveness(self) -> dict[str, str]:
        return {"status": "ok"}

    async def readiness(self) -> dict[str, str]:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ok", "database": "ok"}
        except Exception:
            return {"status": "degraded", "database": "unreachable"}
