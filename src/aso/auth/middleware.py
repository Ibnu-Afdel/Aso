"""Auth middleware (T-38, T-39).

`AuthenticateSession` is a global `web` layer (`foundation/middleware_config.py`): it loads the
user once per request. The rest are route-middleware aliases (`auth`, `guest`, `verified`,
`password.confirm`, `can`).
"""

from __future__ import annotations

import hmac
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aso import context
from aso.exceptions.types import AuthenticationException

__all__ = [
    "Authenticate",
    "AuthenticateSession",
    "Authorize",
    "EnsureEmailIsVerified",
    "RedirectIfAuthenticated",
    "RequirePassword",
]


def _intended_path(request: Any) -> str:
    query = request.url.query
    return request.url.path + (f"?{query}" if query else "")


def _resolve_redirect_target(attr: str | None, fallback_route: str, fallback_path: str) -> str:
    from aso.foundation.application import current_application

    app = current_application()
    target = getattr(app.middleware_config, attr, None) if app is not None and attr else None
    if callable(target):
        ctx = context.current()
        target = target(ctx.request if ctx is not None else None)
    if target:
        return str(target)
    try:
        from aso.routing import route

        return route(fallback_route)
    except Exception:
        return fallback_path


def _wants_json(request: Any) -> bool:
    try:
        from aso.exceptions.handler import handler

        return handler().wants_json(request)
    except Exception:
        return False


class AuthenticateSession:
    """Web-group layer (T-38 "How it works"): loads the user from the session, falling back to
    the "remember me" cookie, and logs out a session whose stored password hash went stale."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await self._resolve_user()

        async def send_with_cookies(message: Message) -> None:
            if message["type"] == "http.response.start":
                ctx = context.current()
                if ctx is not None:
                    headers = list(message.get("headers", []))
                    cookie = ctx.extras.pop("auth.set_remember_cookie", None)
                    if cookie is not None:
                        headers.append((b"set-cookie", cookie.encode("latin-1")))
                    if ctx.extras.pop("auth.forget_remember_cookie", False):
                        from aso.auth.guard import _build_delete_cookie, remember_cookie_name

                        headers.append((b"set-cookie", _build_delete_cookie(remember_cookie_name()).encode("latin-1")))
                    message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cookies)

    async def _resolve_user(self) -> None:
        from aso.auth.guard import _user_model, password_hash_key, session_key

        ctx = context.current()
        if ctx is None or ctx.session is None:
            return
        user_id = ctx.session.get(session_key())
        if user_id is not None:
            model_cls = _user_model()
            user = await model_cls.find(user_id)
            if user is None:
                ctx.session.forget(session_key(), password_hash_key())
                ctx.user = None
                return
            stored_hash = ctx.session.get(password_hash_key())
            if stored_hash is not None and stored_hash != user.password:
                # The password changed elsewhere ("log out other devices", T-38).
                ctx.session.forget(session_key(), password_hash_key())
                ctx.user = None
                return
            ctx.user = user
            return
        ctx.user = None
        await self._try_remember(ctx)

    async def _try_remember(self, ctx: context.RequestContext) -> None:
        from aso.auth.guard import _user_model, auth, remember_cookie_name

        request = ctx.request
        if request is None:
            return
        raw = request.cookies.get(remember_cookie_name())
        if not raw:
            return
        from aso.security.crypt import DecryptException, decrypt

        try:
            payload = decrypt(raw)
        except DecryptException:
            return
        parts = payload.split("|", 2)
        if len(parts) != 3:
            return
        raw_id, remember_token, password_hash = parts
        try:
            user_id: Any = int(raw_id)
        except ValueError:
            user_id = raw_id
        model_cls = _user_model()
        user = await model_cls.find(user_id)
        if user is None:
            return
        stored_token = getattr(user, "remember_token", None) or ""
        if not stored_token or not hmac.compare_digest(stored_token, remember_token):
            return
        if not hmac.compare_digest(user.password or "", password_hash):
            return
        await auth().login(user, remember=False)
        ctx.session.regenerate()  # T-38: a remember-cookie login regenerates the session too
        ctx.extras["auth.via_remember"] = True


class Authenticate:
    """`auth` alias (T-38): a guest raises `AuthenticationException` (the handler sends them to
    `login`, or renders 401 JSON on API requests). Stores the intended URL for `GET` requests."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from aso.auth.guard import auth

        if auth().guest():
            ctx = context.current()
            if ctx is not None and ctx.request is not None and ctx.session is not None and ctx.request.method == "GET":
                ctx.session.put("url.intended", _intended_path(ctx.request))
            raise AuthenticationException()
        await self.app(scope, receive, send)


class RedirectIfAuthenticated:
    """`guest` alias (T-38): a logged-in user is sent to `redirect_users_to()` / route `dashboard`."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from aso.auth.guard import auth

        if auth().check():
            from aso.http.responses import redirect

            target = _resolve_redirect_target("user_redirect", "dashboard", "/dashboard")
            response = redirect(target)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class EnsureEmailIsVerified:
    """`verified` alias (T-38): users with no `email_verified_at` are sent to `verification.notice`."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from aso.auth.guard import auth

        user = auth().user()
        has_verified_email = getattr(user, "has_verified_email", None)
        if user is not None and callable(has_verified_email) and not has_verified_email():
            from aso.http.responses import redirect

            try:
                from aso.routing import route

                target = route("verification.notice")
            except Exception:
                target = "/email/verify"
            response = redirect(target)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class RequirePassword:
    """`password.confirm` alias (T-38): asks for the password again unless it was confirmed
    within `config("auth.password_timeout")` seconds (stored at `session["auth.password_confirmed_at"]`)."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ctx = context.current()
        if ctx is None or ctx.session is None:
            await self.app(scope, receive, send)
            return
        from aso.config import config

        confirmed_at = ctx.session.get("auth.password_confirmed_at")
        timeout = int(config("auth.password_timeout", 10800))
        if confirmed_at is not None and (time.time() - float(confirmed_at)) < timeout:
            await self.app(scope, receive, send)
            return
        if ctx.request is not None and ctx.request.method == "GET":
            ctx.session.put("url.intended", _intended_path(ctx.request))
        if ctx.request is not None and _wants_json(ctx.request):
            from starlette.responses import JSONResponse

            response = JSONResponse({"message": "Password confirmation required."}, status_code=423)
            await response(scope, receive, send)
            return
        from aso.http.responses import redirect

        target = _resolve_redirect_target(None, "password.confirm", "/user/confirm-password")
        response = redirect(target)
        await response(scope, receive, send)


class Authorize:
    """`can:ability,param` alias (T-39): resolves `param` from the route's bound models."""

    def __init__(self, app: ASGIApp, *params: str) -> None:
        self.app = app
        self.params = params

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not self.params:
            raise RuntimeError('The `can:` middleware needs an ability, e.g. `.middleware("can:update,post")`.')
        ability, *param_names = self.params
        ctx = context.current()
        args = [ctx.route_params.get(name) if ctx is not None else None for name in param_names]
        from aso.auth.gate import Gate

        await Gate.authorize(ability, *args)
        await self.app(scope, receive, send)
