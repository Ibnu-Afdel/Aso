"""Unit tests for `aso.auth.events` (T-38, T-46): `Failed` strips the password, `Lockout`
carries only `email`/`ip`, and listeners for these events cannot be queued (they carry a model)."""

from __future__ import annotations

import pytest

from aso.auth.events import Failed, Lockout, Login, Logout, PasswordReset, Registered, Verified
from aso.events import Event
from aso.queue import JobNotSerializable


class _User:
    def __init__(self, id: int) -> None:
        self.id = id


def test_failed_credentials_never_contain_the_password():
    event = Failed(None, {"email": "a@example.com", "password": "secret"})
    assert event.credentials == {"email": "a@example.com"}
    assert event.user is None


def test_lockout_carries_email_and_ip_only():
    event = Lockout(email="a@example.com", ip="1.2.3.4")
    assert event.email == "a@example.com"
    assert event.ip == "1.2.3.4"


def test_login_carries_remember_flag():
    user = _User(1)
    event = Login(user, remember=True)
    assert event.user is user
    assert event.remember is True


@pytest.mark.parametrize("event_cls", [Registered, Verified, PasswordReset, Logout])
def test_single_user_events_carry_the_user(event_cls):
    user = _User(1)
    event = event_cls(user)
    assert event.user is user


async def test_a_queued_listener_on_an_auth_event_raises_job_not_serializable():
    class QueuedListener:
        queued = True

        async def handle(self, event) -> None:  # pragma: no cover - never reached
            raise AssertionError("must not run: dispatch() should raise first")

    Event.listen(Registered, QueuedListener)
    try:
        with pytest.raises(JobNotSerializable):
            await Registered(_User(1)).dispatch()
    finally:
        Event._listeners.pop(Registered, None)
