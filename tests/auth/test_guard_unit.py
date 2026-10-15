"""Unit tests for `auth()` (T-38): `attempt`, `validate`, `login`, `logout`,
`logout_other_devices`, `via_remember`, bypassing HTTP (see `test_auth_app_stack.py` for that)."""

from __future__ import annotations

from sqlalchemy import String

from fastogram.auth import Authenticatable, auth
from fastogram.database import Hashed, Mapped, Model, mapped_column


def _user_model_cls():
    class User(Authenticatable, Model):
        __fillable__ = ["email", "password"]

        email: Mapped[str] = mapped_column(String(255), unique=True)
        password: Mapped[str] = mapped_column(Hashed())
        remember_token: Mapped[str | None] = mapped_column(String(100), nullable=True)

    return User


async def test_attempt_succeeds_with_correct_credentials(db, request_context, user_model):
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await User.create(email="a@example.com", password="correct-horse")
    request_context()

    ok = await auth().attempt({"email": "a@example.com", "password": "correct-horse"})
    assert ok is True
    assert auth().check() is True
    assert auth().user().email == "a@example.com"


async def test_attempt_fails_with_wrong_password_and_dispatches_failed(db, request_context, user_model):
    from fastogram.auth.events import Failed
    from fastogram.events import Event

    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await User.create(email="a@example.com", password="correct-horse")
    request_context()
    Event.fake()

    ok = await auth().attempt({"email": "a@example.com", "password": "wrong"})
    assert ok is False
    assert auth().guest() is True
    Event.assert_dispatched(Failed, lambda e: e.credentials == {"email": "a@example.com"})


async def test_attempt_with_unknown_email_fails_without_leaking_credentials(db, request_context, user_model):
    from fastogram.auth.events import Failed
    from fastogram.events import Event

    user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    request_context()
    Event.fake()

    ok = await auth().attempt({"email": "nobody@example.com", "password": "whatever"})
    assert ok is False
    Event.assert_dispatched(Failed, lambda e: e.user is None)


async def test_validate_does_not_log_in(db, request_context, user_model):
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    await User.create(email="a@example.com", password="correct-horse")
    request_context()

    ok = await auth().validate({"email": "a@example.com", "password": "correct-horse"})
    assert ok is True
    assert auth().guest() is True


async def test_login_sets_user_and_does_not_regenerate_the_session(db, request_context, user_model):
    from fastogram.auth.events import Login
    from fastogram.events import Event

    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(email="a@example.com", password="correct-horse")
    ctx = request_context()
    session_id = ctx.session.id()
    Event.fake()

    await auth().login(user)
    assert auth().user().id == user.id
    assert ctx.session.id() == session_id  # T-38: the caller is responsible for `regenerate()`
    Event.assert_dispatched(Login, lambda e: e.user.id == user.id and e.remember is False)


async def test_logout_clears_user_and_dispatches_logout(db, request_context, user_model):
    from fastogram.auth.events import Logout
    from fastogram.events import Event

    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(email="a@example.com", password="correct-horse")
    request_context()
    Event.fake()

    await auth().login(user)
    old_token = user.remember_token
    await auth().logout()
    assert auth().guest() is True
    assert user.remember_token != old_token  # rotated so "remember me" cookies die too
    Event.assert_dispatched(Logout, lambda e: e.user.id == user.id)


async def test_logout_other_devices_rehashes_the_password(db, request_context, user_model):
    User = user_model(_user_model_cls())
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(email="a@example.com", password="correct-horse")
    request_context()
    await auth().login(user)
    first_hash = user.password

    ok = await auth().logout_other_devices("correct-horse")
    assert ok is True
    assert user.password != first_hash  # fresh salt, invalidates other sessions' stored hash

    wrong = await auth().logout_other_devices("not-the-password")
    assert wrong is False


async def test_via_remember_is_false_by_default(request_context):
    request_context()
    assert auth().via_remember() is False
