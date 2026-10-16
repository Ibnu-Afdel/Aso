"""Sessions, flash data and CSRF helpers (T-18, T-12)."""

from __future__ import annotations

from markupsafe import Markup, escape

from aso import context
from aso.exceptions.types import SessionTooLarge, SessionUnavailable, TokenMismatchException
from aso.session.drivers import clear_array_store, prune_sessions
from aso.session.store import Session

__all__ = [
    "Session",
    "SessionTooLarge",
    "SessionUnavailable",
    "TokenMismatchException",
    "clear_array_store",
    "csrf_field",
    "csrf_token",
    "prune_sessions",
    "session",
]


def session() -> Session:
    """The current request's session. Raises `SessionUnavailable` outside the `web` group."""
    ctx = context.current()
    if ctx is None or ctx.session is None:
        raise SessionUnavailable()
    return ctx.session


def csrf_token() -> str:
    """The current session's CSRF token (T-12). Same value the `XSRF-TOKEN` cookie carries."""
    return session().token()


def csrf_field() -> Markup:
    """`<input type="hidden" name="_token" value="...">` for a plain (non-Inertia) HTML form."""
    return Markup(f'<input type="hidden" name="_token" value="{escape(csrf_token())}">')
