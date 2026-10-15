"""Unit tests for `password_broker()` (T-38): throttling, expiry, and the hashed token.

Uses the `db`/`user_model` fixtures from `conftest.py` directly (no HTTP), so it can simulate an
expired token by rewriting `created_at` -- something the full-stack test in
`test_auth_app_stack.py` cannot do without manipulating real wall-clock time.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from sqlalchemy import String, text

from fastogram.auth import password_broker
from fastogram.config import set_config
from fastogram.database import Hashed, Mapped, Model, mapped_column
from fastogram.database.db import DB


def _user_model_cls():
    class User(Model):
        __fillable__ = ["email", "password"]

        email: Mapped[str] = mapped_column(String(255), unique=True)
        password: Mapped[str] = mapped_column(Hashed())

    return User


async def _create_table(db) -> None:
    await db.execute(
        text(
            "CREATE TABLE password_reset_tokens ("
            "email VARCHAR(255) PRIMARY KEY, token VARCHAR(255) NOT NULL, created_at REAL NOT NULL)"
        )
    )


@contextmanager
def _capture_plaintext_token():
    """The reset token is hashed at rest, so a test that needs the plaintext (to call `reset()`)
    captures it as `ResetPasswordMail` is constructed, exactly once, with the real send path."""
    from fastogram.auth import mail as auth_mail

    captured: dict[str, str] = {}
    original_init = auth_mail.ResetPasswordMail.__init__

    def _init(self, email: str, token: str) -> None:
        captured["token"] = token
        original_init(self, email=email, token=token)

    auth_mail.ResetPasswordMail.__init__ = _init
    try:
        yield captured
    finally:
        auth_mail.ResetPasswordMail.__init__ = original_init


async def test_send_reset_link_creates_a_hashed_token_and_sends_mail(db, user_model):
    from fastogram.mail import Mail

    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    await User.create(email="a@example.com", password="x")
    Mail.fake()

    status = await password_broker().send_reset_link("a@example.com")
    assert status == "sent"

    row = await DB.select_one("SELECT token FROM password_reset_tokens WHERE email = :e", {"e": "a@example.com"})
    assert row is not None
    assert row["token"].startswith("$")  # hashed, not the raw token

    from fastogram.auth.mail import ResetPasswordMail

    Mail.assert_sent(ResetPasswordMail, lambda m: m.has_to("a@example.com"))


async def test_send_reset_link_is_silent_and_sends_nothing_for_an_unknown_email(db, user_model):
    from fastogram.mail import Mail

    user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    Mail.fake()

    status = await password_broker().send_reset_link("nobody@example.com")
    assert status == "sent"  # does not leak whether the email exists
    Mail.assert_nothing_sent()
    row = await DB.select_one("SELECT 1 FROM password_reset_tokens WHERE email = :e", {"e": "nobody@example.com"})
    assert row is None


async def test_send_reset_link_is_throttled_on_a_second_request(db, user_model):
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    await User.create(email="a@example.com", password="x")

    assert await password_broker().send_reset_link("a@example.com") == "sent"
    assert await password_broker().send_reset_link("a@example.com") == "throttled"


async def test_reset_fails_for_an_expired_token(db, user_model):
    set_config(
        "auth.passwords",
        {"users": {"provider": "users", "table": "password_reset_tokens", "expire": 60, "throttle": 60}},
    )
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    await User.create(email="a@example.com", password="old-password")

    with _capture_plaintext_token() as captured:
        assert await password_broker().send_reset_link("a@example.com") == "sent"

    await DB.statement(
        "UPDATE password_reset_tokens SET created_at = :t WHERE email = :e",
        {"t": time.time() - 61 * 60, "e": "a@example.com"},  # 61 minutes ago > 60-minute `expire`
    )

    ok = await password_broker().reset("a@example.com", captured["token"], "new-password")
    assert ok is False


async def test_reset_succeeds_with_a_valid_token_and_fires_password_reset(db, user_model):
    from fastogram.auth.events import PasswordReset
    from fastogram.events import Event

    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    user = await User.create(email="a@example.com", password="old-password")
    Event.fake()

    with _capture_plaintext_token() as captured:
        assert await password_broker().send_reset_link("a@example.com") == "sent"

    ok = await password_broker().reset("a@example.com", captured["token"], "new-password")
    assert ok is True

    refreshed = await User.find(user.id)
    from fastogram.security import hash as hash_

    assert hash_.check("new-password", refreshed.password) is True
    row = await DB.select_one("SELECT 1 FROM password_reset_tokens WHERE email = :e", {"e": "a@example.com"})
    assert row is None  # the token is deleted after use
    Event.assert_dispatched(PasswordReset, lambda e: e.user.id == user.id)


async def test_reset_fails_with_the_wrong_token(db, user_model):
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await _create_table(db)
    await User.create(email="a@example.com", password="old-password")

    await password_broker().send_reset_link("a@example.com")
    ok = await password_broker().reset("a@example.com", "not-the-real-token", "new-password")
    assert ok is False
