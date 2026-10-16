"""`password_broker()` (T-38): create/validate/delete password reset tokens.

Raw SQL through `aso.database.db.DB` against `password_reset_tokens` (one row per email,
upserted), never an ORM model -- the table is provided by the app's migrations (the skeleton's
first migration, like Laravel's), not by this package. Tokens are 64 random characters, stored
**hashed**. `created_at` is a float (unix seconds), to stay driver-agnostic.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

DEFAULT_TABLE = "password_reset_tokens"

__all__ = ["PasswordBroker", "password_broker"]


class PasswordBroker:
    """`password_broker()` returns one of these, bound to a `config/auth.py` `passwords` entry."""

    def __init__(self, provider: str = "users") -> None:
        self.provider = provider

    def _setting(self, key: str, default: Any = None) -> Any:
        from aso.config import config

        return config(f"auth.passwords.{self.provider}.{key}", default)

    def _table(self) -> str:
        return self._setting("table", DEFAULT_TABLE)

    def _expire_seconds(self) -> int:
        return int(self._setting("expire", 60)) * 60

    def _throttle_seconds(self) -> int:
        return int(self._setting("throttle", 60))

    async def send_reset_link(self, email: str) -> str:
        """Create (or refresh) a reset token and mail it. Returns `"sent"` or `"throttled"`.

        The response is the same (`"sent"`) whether or not the email belongs to an account, so a
        caller cannot use it to discover who has one (T-38).
        """
        from aso.database.db import DB

        table = self._table()
        now = time.time()
        row = await DB.select_one(f"SELECT created_at FROM {table} WHERE email = :email", {"email": email})  # noqa: S608
        if row is not None and (now - float(row["created_at"])) < self._throttle_seconds():
            return "throttled"

        from aso.auth.guard import _user_model

        user = await _user_model().where(email=email).first()
        if user is not None:
            from aso.security import hash as hash_

            token = secrets.token_urlsafe(48)
            hashed = await asyncio.to_thread(hash_.make, token)
            await DB.statement(
                f"INSERT INTO {table} (email, token, created_at) VALUES (:email, :token, :now) "  # noqa: S608
                "ON CONFLICT (email) DO UPDATE SET token = :token, created_at = :now",
                {"email": email, "token": hashed, "now": now},
            )

            from aso.auth.mail import ResetPasswordMail
            from aso.mail import Mail

            await Mail.to(email).send(ResetPasswordMail(email=email, token=token))
        return "sent"

    async def reset(self, email: str, token: str, password: str) -> bool:
        """Validate `token`, set the new password, delete the token and fire `PasswordReset`."""
        from aso.database.db import DB

        table = self._table()
        row = await DB.select_one(f"SELECT token, created_at FROM {table} WHERE email = :email", {"email": email})  # noqa: S608
        if row is None:
            return False

        from aso.security import hash as hash_

        valid = await asyncio.to_thread(hash_.check, token, row["token"])
        if not valid or (time.time() - float(row["created_at"])) > self._expire_seconds():
            return False

        from aso.auth.guard import _user_model

        user = await _user_model().where(email=email).first()
        if user is None:
            return False
        user.password = password  # the `Hashed` column hashes it on assignment (T-31, T-40)
        user.remember_token = secrets.token_urlsafe(45)  # logs out "remember me" elsewhere
        await user.save()
        await DB.statement(f"DELETE FROM {table} WHERE email = :email", {"email": email})  # noqa: S608

        from aso.auth.events import PasswordReset

        await PasswordReset(user).dispatch()
        return True


_brokers: dict[str, PasswordBroker] = {}


def password_broker(name: str | None = None) -> PasswordBroker:
    from aso.config import config

    key = name or config("auth.defaults.passwords", "users")
    broker = _brokers.get(key)
    if broker is None:
        broker = PasswordBroker(key)
        _brokers[key] = broker
    return broker


def _reset_for_tests() -> None:
    _brokers.clear()
