from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.routes.health import router as health_router
from app.bootstrap.container import (
    get_telegram_webhook_app_service,
    initialize_logging,
)
from app.bootstrap.request_context import get_request_id
from app.bootstrap.request_id_middleware import add_request_id_middleware
from app.bootstrap.startup_checks import run_startup_checks
from app.bot.dispatcher import get_dispatcher
from app.core.config import get_settings
from app.core.db import engine
from app.integrations.telegram import setup_telegram, teardown_telegram

settings = get_settings()

dp = get_dispatcher() if settings.bot_enabled else None
bot = dp.bot if dp is not None else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_logging()
    await run_startup_checks(settings, engine)
    app.state.polling_task = None
    if settings.bot_enabled and dp is not None and bot is not None:
        app.state.polling_task = await setup_telegram(bot, dp)
    yield
    if settings.bot_enabled and bot is not None:
        await teardown_telegram(bot, app.state.polling_task)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
add_request_id_middleware(app)

app.include_router(health_router)


@app.post("/bot/webhook")
async def telegram_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        return JSONResponse(status_code=403, content={"error": "invalid_secret"})
    return await get_telegram_webhook_app_service().handle_request(
        await request.json(),
        bot_enabled=settings.bot_enabled,
        dispatcher=dp,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.bind(
        request_id=get_request_id(),
        event_type="unhandled_exception",
        path=request.url.path,
        method=request.method,
    ).exception("Unhandled application exception")
    content: dict[str, str] = {"error": "internal_error"}
    if settings.debug:
        content["trace"] = "".join(traceback.format_exception(exc))
    return JSONResponse(status_code=500, content=content)
