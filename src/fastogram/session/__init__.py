"""Sessions and flash data (T-18)."""

from __future__ import annotations

from fastogram import context
from fastogram.exceptions.types import SessionTooLarge, SessionUnavailable
from fastogram.session.store import Session

__all__ = ["Session", "SessionTooLarge", "SessionUnavailable", "session"]


def session() -> Session:
    """The current request's session. Raises `SessionUnavailable` outside the `web` group."""
    ctx = context.current()
    if ctx is None or ctx.session is None:
        raise SessionUnavailable()
    return ctx.session
