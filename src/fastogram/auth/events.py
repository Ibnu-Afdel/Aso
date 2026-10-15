"""Authentication events (T-38, T-46): `from fastogram.auth.events import ...`.

These carry the `User` model, so **their listeners cannot be queued** (`fastogram.events.Event.
dispatch()` raises `JobNotSerializable` before running anything if any listener sets
`queued = True`, T-46). `Failed.credentials` never contains the password; `Lockout` carries the
email and IP instead of the whole request.
"""

from __future__ import annotations

from typing import Any

from fastogram.events import Event

__all__ = ["Failed", "Lockout", "Login", "Logout", "PasswordReset", "Registered", "Verified"]


class Registered(Event):
    """A user registered (T-38). Carries `user`."""

    def __init__(self, user: Any) -> None:
        self.user = user


class Verified(Event):
    """A user's email address was verified (T-38). Carries `user`."""

    def __init__(self, user: Any) -> None:
        self.user = user


class PasswordReset(Event):
    """A user reset their password through the password broker (T-38). Carries `user`."""

    def __init__(self, user: Any) -> None:
        self.user = user


class Login(Event):
    """A user logged in (T-38). Carries `user` and whether it was a "remember me" login."""

    def __init__(self, user: Any, remember: bool = False) -> None:
        self.user = user
        self.remember = remember


class Logout(Event):
    """A user logged out (T-38). Carries `user`."""

    def __init__(self, user: Any) -> None:
        self.user = user


class Failed(Event):
    """`auth().attempt()`/`.validate()` rejected credentials (T-38). `user` is `None` when no
    matching account was found. `credentials` never includes the password."""

    def __init__(self, user: Any, credentials: dict[str, Any]) -> None:
        self.user = user
        self.credentials = {k: v for k, v in credentials.items() if k != "password"}


class Lockout(Event):
    """The login rate limit was hit (T-38). Carries `email` and `ip` (not the whole request)."""

    def __init__(self, email: str, ip: str | None) -> None:
        self.email = email
        self.ip = ip
