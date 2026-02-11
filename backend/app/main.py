from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.health import router as health_router
from app.bot.dispatcher import get_dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.integrations.telegram import setup_telegram_webhook, teardown_telegram_webhook
from app.services.telegram_webhook import TelegramWebhookAppService

settings = get_settings()

dp = get_dispatcher() if settings.bot_enabled else None
telegram_webhook_service = TelegramWebhookAppService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.bot_enabled and dp is not None:
        await setup_telegram_webhook(dp)
    yield
    if settings.bot_enabled and dp is not None:
        await teardown_telegram_webhook(dp)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)


@app.post("/bot/webhook")
async def telegram_webhook(request: Request):
    if not settings.bot_enabled or dp is None:
        return JSONResponse(
            status_code=503,
            content={"error": "telegram_bot_disabled"},
        )
    try:
        await telegram_webhook_service.handle_update(dp, await request.json())
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {"ok": True}


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(_: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=500, content={"error": "database_error", "details": str(exc)})
