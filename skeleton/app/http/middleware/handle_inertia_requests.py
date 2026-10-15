"""Shares data available on (almost) every page (T-17)."""

from fastogram.config import config
from fastogram.http import Request
from fastogram.inertia import InertiaMiddleware


class HandleInertiaRequests(InertiaMiddleware):
    root_view = "app.html"  # resources/views/app.html

    async def share(self, request: Request) -> dict:
        return {
            **await super().share(request),
            "name": config("app.name"),
            "auth": {"user": request.user()},
            "sidebarOpen": request.cookie("sidebar_state") != "false",
        }
