from __future__ import annotations

from fastogram.auth import auth
from fastogram.config import config
from fastogram.inertia import InertiaMiddleware


class HandleInertiaRequests(InertiaMiddleware):
    async def share(self, request) -> dict:
        user = auth().user()
        return {
            **await super().share(request),
            "name": config("app.name"),
            "auth": {"user": {"id": user.id, "name": user.name} if user is not None else None},
        }
