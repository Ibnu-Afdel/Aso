"""Structured logging (T-22): `log.debug/info/notice/warning/error/critical(msg, **context)`.

The guide page says FastoGram "wraps loguru". This implementation instead sits directly on
Python's standard `logging` module: adding `loguru` as a dependency means editing `pyproject.toml`,
which is outside this package's file scope (see the final report's "exact changes needed outside
my files"). Using named, non-root loggers (`fastogram.channel.<name>`) gives the same observable
contract — channels, request id correlation, redaction, a test `LogCapture` — without ever calling
`logging.basicConfig()` or touching the root logger's handlers, so pytest's `caplog` (which also
listens on the root logger) is never disturbed. `configure_logging()` only bumps a generation
counter; each channel's handlers are (re)built lazily, on the next log call, from the config that
is current *then* — which is what makes it safe to call again after a second `create_app()`.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

__all__ = ["ChannelLogger", "Log", "configure_logging", "log"]

LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
#: Laravel's RFC 5424 levels that are not one of our five: mapped onto the nearest one.
LEVEL_ALIASES: dict[str, str] = {"notice": "info", "alert": "critical", "emergency": "critical"}

KNOWN_DRIVERS = {"stack", "single", "daily", "stderr"}

DEFAULT_REDACT = ["password", "password_confirmation", "current_password", "token", "secret", "authorization", "cookie"]

_generation = 0
_channel_generation: dict[str, int] = {}


def configure_logging() -> None:
    """Invalidate every channel's cached handlers, so the next log call rebuilds them from the
    config that is current *then*. Idempotent, and safe to call again after another `create_app()`.
    """
    global _generation
    _generation += 1


def _redact(ctx: dict[str, Any]) -> dict[str, Any]:
    from fastogram.config import config

    keys = {str(k).lower() for k in (config("logging.redact", DEFAULT_REDACT) or DEFAULT_REDACT)}
    return {k: ("[redacted]" if str(k).lower() in keys else v) for k, v in ctx.items()}


def _request_id() -> str:
    from fastogram import context as context_module

    ctx = context_module.current()
    if ctx is None:
        return "-"
    state = (ctx.scope or {}).get("state") or {}
    return state.get("request_id") or "-"


def _default_channel() -> str:
    from fastogram.config import config
    from fastogram.foundation import environment

    fallback = "stack" if not environment("production") and not environment("testing") else "stderr"
    return str(config("logging.default", fallback))


def _log_dir() -> Path:
    from fastogram.foundation import paths

    return paths.storage_path("logs")


def _file_handler(filename: str, daily: bool = False) -> logging.Handler:
    try:
        directory = _log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        if daily:
            return logging.handlers.TimedRotatingFileHandler(path, when="midnight", backupCount=14, encoding="utf-8")
        return logging.FileHandler(path, encoding="utf-8")
    except OSError:  # pragma: no cover - defensive: never fail boot over a log file
        return logging.StreamHandler(sys.stderr)


def _handlers_for(driver: str, spec: dict[str, Any], is_prod: bool) -> list[logging.Handler]:
    filename = spec.get("path", "app.log")
    if driver == "stack":
        members = spec.get("channels") or ["stderr", "single"]
        handlers: list[logging.Handler] = []
        for member in members:
            handlers.extend(_handlers_for(member, {}, is_prod))
        return handlers or [logging.StreamHandler(sys.stdout)]
    if driver == "stderr":
        return [logging.StreamHandler(sys.stderr)]
    if driver == "daily":
        return [_file_handler(filename, daily=True)]
    # "single" and any unrecognised driver default to one file (defaults when a channel is missing)
    return [_file_handler(filename)]


class _Formatter(logging.Formatter):
    """Human-readable lines locally; single-line JSON (`serialize=True` equivalent) in production."""

    def __init__(self, channel: str, is_prod: bool) -> None:
        super().__init__()
        self.channel_name = channel
        self.is_prod = is_prod

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None) or "-"
        ctx: dict[str, Any] = getattr(record, "context", None) or {}
        if self.is_prod:
            payload = {
                "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "channel": self.channel_name,
                "request_id": request_id,
                "message": record.getMessage(),
                **ctx,
            }
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            return json.dumps(payload, default=str)
        line = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} [{record.levelname}] [{request_id}] {record.getMessage()}"
        if ctx:
            line += f" {json.dumps(ctx, default=str)}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def _ensure_channel(name: str) -> logging.Logger:
    """The stdlib logger for one channel, with handlers matching current config.

    Rebuilt lazily whenever `configure_logging()` has bumped the generation counter since the
    handlers were last installed; never touches any logger outside the `fastogram.channel.*`
    namespace, and always keeps `propagate = True` so pytest's `caplog` still sees every record.
    """
    logger = logging.getLogger(f"fastogram.channel.{name}")
    if _channel_generation.get(name) == _generation:
        return logger
    for handler in list(logger.handlers):
        if getattr(handler, "_fastogram_managed", False):
            logger.removeHandler(handler)

    from fastogram.config import config
    from fastogram.foundation import environment

    is_prod = bool(environment("production"))
    level_name = str(config("logging.level", "info" if is_prod else "debug")).lower()
    logger.setLevel(LEVELS.get(level_name, logging.DEBUG))
    logger.propagate = True

    channels_cfg = config("logging.channels", {}) or {}
    spec = channels_cfg.get(name, {}) if isinstance(channels_cfg, dict) else {}
    driver = spec.get("driver", name if name in KNOWN_DRIVERS else "single")
    for handler in _handlers_for(driver, spec, is_prod):
        handler._fastogram_managed = True  # type: ignore[attr-defined]
        handler.setFormatter(_Formatter(name, is_prod))
        logger.addHandler(handler)
    _channel_generation[name] = _generation
    return logger


class ChannelLogger:
    """One channel: `log.channel("orders").warning(...)`."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def _emit(self, level: str, message: str, **context: Any) -> None:
        exc_info = context.pop("exc_info", None)
        resolved = LEVEL_ALIASES.get(level, level)
        logger = _ensure_channel(self.channel)
        logger.log(LEVELS[resolved], message, exc_info=exc_info, extra={"context": _redact(context), "request_id": _request_id()})

    def debug(self, message: str, **context: Any) -> None:
        self._emit("debug", message, **context)

    def info(self, message: str, **context: Any) -> None:
        self._emit("info", message, **context)

    def notice(self, message: str, **context: Any) -> None:
        self._emit("notice", message, **context)

    def warning(self, message: str, **context: Any) -> None:
        self._emit("warning", message, **context)

    def error(self, message: str, **context: Any) -> None:
        self._emit("error", message, **context)

    def critical(self, message: str, **context: Any) -> None:
        self._emit("critical", message, **context)

    def alert(self, message: str, **context: Any) -> None:
        self._emit("alert", message, **context)

    def emergency(self, message: str, **context: Any) -> None:
        self._emit("emergency", message, **context)


class Log:
    """`from fastogram.log import log`: logs to `config("logging.default")` (T-22).

    Not a fixed channel: the default channel is resolved fresh on every call, since config may
    change between a test's `create_app()` calls.
    """

    def channel(self, name: str) -> ChannelLogger:
        return ChannelLogger(name)

    def debug(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).debug(message, **context)

    def info(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).info(message, **context)

    def notice(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).notice(message, **context)

    def warning(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).warning(message, **context)

    def error(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).error(message, **context)

    def critical(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).critical(message, **context)

    def alert(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).alert(message, **context)

    def emergency(self, message: str, **context: Any) -> None:
        self.channel(_default_channel()).emergency(message, **context)


log = Log()
