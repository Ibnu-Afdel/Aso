import json
import logging
import sys

from loguru import logger

from app.bootstrap.request_context import get_request_id
from app.core.config import Settings

_configured = False


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def _patch_record(record: dict) -> dict:
    extra = record.setdefault("extra", {})
    extra.setdefault("request_id", get_request_id())
    extra.setdefault("event_type", None)
    extra.setdefault("path", None)
    extra.setdefault("method", None)
    extra.setdefault("user_id", None)
    return record


def _dev_formatter(record: dict) -> str:
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "rid={extra[request_id]} | "
        "event={extra[event_type]} | "
        "{name}:{function}:{line} - {message}\n"
    )


def _prod_sink(message) -> None:
    record = message.record
    payload = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "request_id": record["extra"].get("request_id"),
        "event_type": record["extra"].get("event_type"),
        "path": record["extra"].get("path"),
        "method": record["extra"].get("method"),
        "user_id": record["extra"].get("user_id"),
        "exception": str(record["exception"]) if record["exception"] else None,
    }
    print(json.dumps(payload, ensure_ascii=True), file=sys.stdout)


def configure_logging(settings: Settings) -> None:
    global _configured
    if _configured:
        return

    logger.remove()
    logger.configure(patcher=_patch_record)

    if settings.environment.lower() == "production":
        logger.add(_prod_sink, level="INFO", backtrace=False, diagnose=False)
    else:
        logger.add(sys.stdout, level="DEBUG", colorize=True, format=_dev_formatter)

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    _configured = True
