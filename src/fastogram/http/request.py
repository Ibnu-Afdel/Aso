"""`fastogram.http.Request` (T-14).

SEED (spine): body cache shared through the ASGI scope + `receive_replay()`. The http package
task completes the Laravel-style API (`input`, `query`, `header`, `user`, `session`, ...).
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request as StarletteRequest
from starlette.types import Message, Receive

_BODY_KEY = "fastogram.body"


class Request(StarletteRequest):
    """A Starlette request whose body is cached in the scope, so every Request object built for
    the same ASGI scope (middleware, FastAPI's own, ours) can read the body again."""

    async def body(self) -> bytes:
        cached = self.scope.get(_BODY_KEY)
        if cached is not None:
            return cached
        body = await super().body()
        self.scope[_BODY_KEY] = body
        return body

    def receive_replay(self, receive: Receive) -> Receive:
        """A `receive` that replays the cached body once it has been read by anyone."""
        scope = self.scope
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            cached = scope.get(_BODY_KEY)
            if cached is not None and not replayed:
                replayed = True
                return {"type": "http.request", "body": cached, "more_body": False}
            if cached is not None and replayed:
                # body already delivered; wait for disconnect like Starlette does
                return await receive()
            return await receive()

        return replay

    # Laravel-style helpers used by the spine; completed by the http package task.
    def header(self, name: str, default: Any = None) -> Any:
        return self.headers.get(name, default)

    def inertia(self) -> bool:
        return self.headers.get("x-inertia") == "true"

    def session(self) -> Any:
        from fastogram.session import session

        return session()

    def user(self) -> Any:
        try:
            from fastogram.auth import auth
        except ImportError:
            return None
        return auth().user()
