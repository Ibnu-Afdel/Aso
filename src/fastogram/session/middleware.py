"""`StartSession` (T-18). SEED (spine): array driver, unsigned id cookie.

The session package task completes: signed id cookie, database/cookie/array drivers, lifetime,
lottery, `_previous_url` rules, cookie attributes from config, write-skipping, `SessionTooLarge`.
"""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastogram import context
from fastogram.session.store import Session, new_id

ARRAY_STORE: dict[str, dict[str, Any]] = {}


def cookie_name() -> str:
    from fastogram.config import config

    return config("session.cookie") or "fastogram-session"


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


class StartSession:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ctx = context.current()
        if scope["type"] != "http" or ctx is None:
            await self.app(scope, receive, send)
            return
        name = cookie_name()
        sid = _cookies(scope).get(name)
        if sid and sid in ARRAY_STORE:
            session = Session(sid, json.loads(json.dumps(ARRAY_STORE[sid])), is_new=False)
        else:
            session = Session(new_id())
        ctx.session = session
        prefetch = _header(scope, b"purpose") == "prefetch"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                if (
                    scope["method"] == "GET"
                    and status == 200
                    and not prefetch
                    and _header(scope, b"x-inertia-partial-data") is None
                ):
                    qs = scope.get("query_string", b"").decode("latin-1")
                    session.put("_previous_url", scope["path"] + (f"?{qs}" if qs else ""))
                if not prefetch:
                    session.age_flash()
                if session.previous_id:
                    ARRAY_STORE.pop(session.previous_id, None)
                ARRAY_STORE[session.id()] = session.data
                cookie = f"{name}={session.id()}; Path=/; HttpOnly; SameSite=lax"
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie.encode("latin-1"))]
            await send(message)

        await self.app(scope, receive, send_wrapper)
