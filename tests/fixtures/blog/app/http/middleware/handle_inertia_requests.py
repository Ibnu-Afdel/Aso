from aso.config import config
from aso.inertia import InertiaMiddleware


class HandleInertiaRequests(InertiaMiddleware):
    async def share(self, request) -> dict:
        return {**await super().share(request), "name": config("app.name")}
