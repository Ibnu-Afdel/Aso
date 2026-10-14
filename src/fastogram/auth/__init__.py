"""Authentication and authorization (T-38, T-39). SEED (spine)."""

from __future__ import annotations

from typing import Any

from fastogram import context
from fastogram.exceptions.types import AuthenticationException, AuthorizationException

__all__ = ["AuthenticationException", "AuthorizationException", "auth"]


class _Guard:
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
        user = self.user()
        return getattr(user, "id", None)


def auth() -> _Guard:
    return _Guard()
