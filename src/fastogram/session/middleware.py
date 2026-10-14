"""`StartSession` (T-18): signed id cookie, `array`/`database`/`cookie` drivers, flash ageing,
`_previous_url`, write-skipping, the pruning lottery.
"""

from __future__ import annotations

import random
import time
from http.cookies import SimpleCookie
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context
from fastogram.session.configuration import SessionSettings, settings
from fastogram.session.drivers import (
    DatabaseDriver,
    SessionRecord,
    array_driver,
    decode_cookie_payload,
    encode_cookie_payload,
    sign_id,
    unsign_id,
)
from fastogram.session.store import Session, new_id


def cookie_name() -> str:
    """Public helper kept for anything that only needs the cookie name (e.g. the test plugin)."""
    return settings().cookie


def _cookies(scope: Scope) -> dict[str, str]:
    raw = b"; ".join(v for k, v in scope.get("headers", []) if k == b"cookie").decode("latin-1")
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return {}
    return {k: m.value for k, m in jar.items()}


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return None


async def _load_session(cfg: SessionSettings, raw_cookie: str | None) -> Session:
    if cfg.driver == "cookie":
        record = decode_cookie_payload(raw_cookie)
        if record is None:
            return Session(new_id())
        return Session(record.id, record.data, is_new=False, last_activity=record.last_activity)

    sid = unsign_id(raw_cookie)
    if sid is None:
        return Session(new_id())
    driver = DatabaseDriver(cfg.table) if cfg.driver == "database" else array_driver()
    record = await driver.load(sid, cfg.lifetime * 60)
    if record is None:
        return Session(new_id())
    return Session(record.id, record.data, is_new=False, last_activity=record.last_activity)


async def _persist(cfg: SessionSettings, session: Session, meta: dict[str, Any]) -> str:
    """Persist (if needed) and return the cookie *value* to send (signed id, or ciphertext)."""
    now_ts = int(time.time())
    stale = (now_ts - session.last_activity) > 60
    should_write = session.dirty or stale

    if cfg.driver == "cookie":
        record = SessionRecord(session.id(), session.data, now_ts if should_write else session.last_activity)
        if should_write:
            session.last_activity = now_ts
            session.dirty = False
        return encode_cookie_payload(record)

    driver = DatabaseDriver(cfg.table) if cfg.driver == "database" else array_driver()
    if should_write:
        session.last_activity = now_ts
        record = SessionRecord(session.id(), session.data, now_ts)
        await driver.save(record, **meta)
        session.dirty = False
    if session.destroy_previous and session.previous_id:
        await driver.delete(session.previous_id)
    if cfg.driver == "database" and random.randint(1, cfg.lottery[1]) <= cfg.lottery[0]:
        from fastogram.session.drivers import prune_sessions

        await prune_sessions(cfg.table)
    return sign_id(session.id())


def _build_set_cookie(name: str, value: str, cfg: SessionSettings) -> str:
    parts = [f"{name}={value}", f"Path={cfg.path}"]
    if cfg.domain:
        parts.append(f"Domain={cfg.domain}")
    if cfg.secure:
        parts.append("Secure")
    if cfg.http_only:
        parts.append("HttpOnly")
    parts.append(f"SameSite={cfg.same_site}")
    if not cfg.expire_on_close:
        parts.append(f"Max-Age={cfg.lifetime * 60}")
    return "; ".join(parts)


def _should_store_previous_url(scope: Scope, status: int, prefetch: bool) -> bool:
    if scope["method"] != "GET" or status != 200 or prefetch:
        return False
    if _header(scope, b"x-inertia-partial-data") is not None:
        return False
    # NOTE: T-18 also asks for "matched route". `context.RequestContext.route` is written by the
    # routing package's pipeline, which was not wired up yet at the time this was written -- see
    # the "Decisions I made" note in this task's report.
    return True


class StartSession:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ctx = context.current()
        if ctx is None:
            await self.app(scope, receive, send)
            return

        cfg = settings()
        raw_cookie = _cookies(scope).get(cfg.cookie)
        session = await _load_session(cfg, raw_cookie)
        ctx.session = session
        prefetch = _header(scope, b"purpose") == "prefetch"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                if _should_store_previous_url(scope, status, prefetch):
                    qs = scope.get("query_string", b"").decode("latin-1")
                    session.put("_previous_url", scope["path"] + (f"?{qs}" if qs else ""))
                if not prefetch:
                    session.age_flash()

                user = getattr(ctx, "user", None)
                user_id = getattr(user, "id", None) if user not in (None, context.UNRESOLVED) else None
                client = scope.get("client")
                meta = {
                    "user_id": user_id,
                    "ip_address": client[0] if client else None,
                    "user_agent": _header(scope, b"user-agent"),
                }
                cookie_value = await _persist(cfg, session, meta)
                cookie_header = _build_set_cookie(cfg.cookie, cookie_value, cfg)
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie_header.encode("latin-1"))]
            await send(message)

        await self.app(scope, receive, send_wrapper)
