from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.health import router as health_router
from app.bootstrap.container import get_telegram_webhook_app_service
from app.bootstrap.session_middleware import add_session_middleware
from app.bot.dispatcher import get_dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.integrations.telegram import setup_telegram_webhook, teardown_telegram_webhook

settings = get_settings()

dp = get_dispatcher() if settings.bot_enabled else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.bot_enabled and dp is not None:
        await setup_telegram_webhook(dp)
    yield
    if settings.bot_enabled and dp is not None:
        await teardown_telegram_webhook(dp)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
add_session_middleware(app)

app.include_router(health_router)


@app.post("/bot/webhook")
async def telegram_webhook(request: Request):
    return await get_telegram_webhook_app_service().handle_request(
        await request.json(),
        bot_enabled=settings.bot_enabled,
        dispatcher=dp,
    )


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(_: Request, exc: SQLAlchemyError):
    return JSONResponse(status_code=500, content={"error": "database_error", "details": str(exc)})
