"""`config/session.py` settings, with sane defaults when a key is missing (T-18).

A real skeleton's `config/session.py` sets every key (see the guide page). Test fixtures often
set only `driver` and `cookie`, so every other value here has a Laravel-matching default.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SessionSettings:
    driver: str
    lifetime: int  # minutes
    expire_on_close: bool
    table: str
    lottery: tuple[int, int]
    cookie: str
    path: str
    domain: str | None
    secure: bool
    http_only: bool
    same_site: str
    dont_flash: list[str] = field(default_factory=list)


def default_cookie_name() -> str:
    from fastogram.config import config
    from fastogram.support import slug

    return slug(config("app.name", "fastogram")) + "-session"


def settings() -> SessionSettings:
    from fastogram.config import config

    secure_cfg = config("session.secure", None)
    secure = secure_cfg if secure_cfg is not None else str(config("app.url", "")).startswith("https")
    lottery_cfg = config("session.lottery", (2, 100))
    return SessionSettings(
        driver=config("session.driver", "database"),
        lifetime=int(config("session.lifetime", 120)),
        expire_on_close=bool(config("session.expire_on_close", False)),
        table=config("session.table", "sessions"),
        lottery=(int(lottery_cfg[0]), int(lottery_cfg[1])),
        cookie=config("session.cookie") or default_cookie_name(),
        path=config("session.path", "/"),
        domain=config("session.domain", None),
        secure=bool(secure),
        http_only=bool(config("session.http_only", True)),
        same_site=config("session.same_site", "lax"),
        dont_flash=list(config("session.dont_flash", ["password", "password_confirmation", "current_password"])),
    )
