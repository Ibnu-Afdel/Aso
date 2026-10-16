"""`auth()`: the session guard (T-38).

`user()`/`id()`/`check()`/`guest()`/`via_remember()` are synchronous: the user is loaded once per
web request by `AuthenticateSession` (`middleware.py`) and cached on `context.current().user`.
Everything that may touch the database or hash a password is `async`.

`login()`/`logout()` do **not** call `session().regenerate()`/`.invalidate()` themselves (T-38:
"Always call `session().regenerate()` after `login()` and `session().invalidate()` after
`logout()`. The kit's controllers do this."); the one exception is a "remember me" cookie login,
which `AuthenticateSession` regenerates itself since there is no controller in that path.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import Any

from aso import context
from aso.exceptions.types import AuthenticationException, AuthorizationException

__all__ = ["AuthenticationException", "AuthorizationException", "auth"]


def guard_name() -> str:
    from aso.config import config

    return config("auth.defaults.guard", "web")


def session_key() -> str:
    return f"login_{guard_name()}"


def password_hash_key() -> str:
    return f"password_hash_{guard_name()}"


def remember_cookie_name() -> str:
    return f"remember_{guard_name()}"


def _import_path(path: str) -> Any:
    import importlib

    module_path, _, attr = path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _user_model() -> type:
    """The user model class, resolved from the guard's provider (`config/auth.py`, T-38)."""
    from aso.config import config

    guard = guard_name()
    provider = config(f"auth.guards.{guard}.provider", "users")
    path = config(f"auth.providers.{provider}.model", "app.models.user.User")
    return _import_path(path)


def _is_https() -> bool:
    from aso.config import config

    return str(config("app.url") or "").startswith("https://")


def _build_set_cookie(name: str, value: str, *, max_age: int) -> str:
    from starlette.responses import Response as StarletteResponse

    resp = StarletteResponse()
    resp.set_cookie(key=name, value=value, max_age=max_age, path="/", httponly=True, samesite="lax", secure=_is_https())
    for key, raw in resp.raw_headers:
        if key == b"set-cookie":
            return raw.decode("latin-1")
    raise RuntimeError("Could not build a Set-Cookie header.")  # pragma: no cover - defensive


def _build_delete_cookie(name: str) -> str:
    from starlette.responses import Response as StarletteResponse

    resp = StarletteResponse()
    resp.delete_cookie(key=name, path="/")
    for key, raw in resp.raw_headers:
        if key == b"set-cookie":
            return raw.decode("latin-1")
    raise RuntimeError("Could not build a Set-Cookie header.")  # pragma: no cover - defensive


class _Guard:
    """What `auth()` returns. One per call -- all state lives in `context.current()`."""

    # ------------------------------------------------------------ sync reads

    def user(self) -> Any:
        ctx = context.current()
        if ctx is None or ctx.user is context.UNRESOLVED:
            return None
        return ctx.user

    def check(self) -> bool:
        return self.user() is not None

    def guest(self) -> bool:
        return self.user() is None

    def id(self) -> Any:
        return getattr(self.user(), "id", None)

    def via_remember(self) -> bool:
        ctx = context.current()
        return bool(ctx is not None and ctx.extras.get("auth.via_remember", False))

    # ------------------------------------------------------------ async

    async def attempt(self, credentials: dict[str, Any], remember: bool = False) -> bool:
        from aso.auth.events import Failed
        from aso.security import hash as hash_

        password = str(credentials.get("password", ""))
        lookup = {k: v for k, v in credentials.items() if k != "password"}
        model_cls = _user_model()
        user = await model_cls.where(**lookup).first() if lookup else None
        stored_hash = getattr(user, "password", None) if user is not None else None
        # Always run `hash.check` (even with a dummy hash when no user was found) so the
        # response time does not reveal whether the email exists (T-38 "How it works").
        valid = await asyncio.to_thread(hash_.check, password, stored_hash or _dummy_hash())
        if user is None or not valid:
            await Failed(user, credentials).dispatch()
            return False
        if await asyncio.to_thread(hash_.needs_rehash, stored_hash):
            user.password = password  # the `Hashed` column re-hashes on assignment (T-40, T-31)
            await user.save()
        await self.login(user, remember=remember)
        return True

    async def validate(self, credentials: dict[str, Any]) -> bool:
        from aso.security import hash as hash_

        password = str(credentials.get("password", ""))
        lookup = {k: v for k, v in credentials.items() if k != "password"}
        model_cls = _user_model()
        user = await model_cls.where(**lookup).first() if lookup else None
        stored_hash = getattr(user, "password", None) if user is not None else None
        valid = await asyncio.to_thread(hash_.check, password, stored_hash or _dummy_hash())
        return user is not None and valid

    async def login(self, user: Any, remember: bool = False) -> None:
        from aso.auth.events import Login
        from aso.session import session as get_session

        s = get_session()
        s.put(session_key(), user.id)
        s.put(password_hash_key(), user.password)
        ctx = context.current()
        if ctx is not None:
            ctx.user = user
        if remember:
            await self._remember(user)
        await Login(user, remember).dispatch()

    async def login_using_id(self, user_id: Any, remember: bool = False) -> Any:
        model_cls = _user_model()
        user = await model_cls.find(user_id)
        if user is not None:
            await self.login(user, remember=remember)
        return user

    async def logout(self) -> None:
        from aso.auth.events import Logout
        from aso.session import session as get_session

        user = self.user()
        try:
            s = get_session()
            s.forget(session_key(), password_hash_key())
        except Exception:
            pass
        ctx = context.current()
        if ctx is not None:
            ctx.user = None
            ctx.extras.pop("auth.via_remember", None)
        if user is not None:
            # Rotate `remember_token` so "remember me" cookies elsewhere stop working too.
            user.remember_token = secrets.token_urlsafe(45)
            await user.save()
        self._forget_remember_cookie()
        if user is not None:
            await Logout(user).dispatch()

    async def logout_other_devices(self, password: str) -> bool:
        from aso.security import hash as hash_

        user = self.user()
        if user is None:
            return False
        valid = await asyncio.to_thread(hash_.check, password, user.password)
        if not valid:
            return False
        user.password = password  # re-hash with a fresh salt: other sessions' stored hash goes stale
        await user.save()
        try:
            from aso.session import session as get_session

            get_session().put(password_hash_key(), user.password)
        except Exception:
            pass
        return True

    # ------------------------------------------------------------ remember-me cookie

    async def _remember(self, user: Any) -> None:
        from aso.config import config
        from aso.security import crypt

        if not getattr(user, "remember_token", None):
            user.remember_token = secrets.token_urlsafe(45)
            await user.save()
        payload = f"{user.id}|{user.remember_token}|{user.password}"
        token = crypt.encrypt(payload)
        minutes = int(config("auth.remember_lifetime", 60 * 24 * 400))
        header = _build_set_cookie(remember_cookie_name(), token, max_age=minutes * 60)
        ctx = context.current()
        if ctx is not None:
            ctx.extras["auth.set_remember_cookie"] = header

    def _forget_remember_cookie(self) -> None:
        ctx = context.current()
        if ctx is not None:
            ctx.extras["auth.forget_remember_cookie"] = True


_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    """A real (but useless) hash to check against when no user was found, so a failed login by
    an unknown email takes the same time as one by a known email (T-38 "How it works")."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        from aso.security import hash as hash_

        _DUMMY_HASH = hash_.make(secrets.token_urlsafe(32))
    return _DUMMY_HASH


def auth() -> _Guard:
    return _Guard()
