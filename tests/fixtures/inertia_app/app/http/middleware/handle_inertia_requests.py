from aso.config import config
from aso.inertia import InertiaMiddleware


class HandleInertiaRequests(InertiaMiddleware):
    async def share(self, request) -> dict:
        return {
            **await super().share(request),
            "name": config("app.name"),
            "auth.user": lambda: {"id": 1, "name": "Ada"},
        }

    async def share_once(self, request) -> dict:
        return {
            **await super().share_once(request),
            "countries": lambda: ["US", "NL"],
        }
