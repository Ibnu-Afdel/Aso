from aso import context
from aso.http import Controller


class GroupController(Controller):
    """Used by the route-group tests (prefix/name/middleware nesting, controller groups, T-10)."""

    async def index(self):
        ctx = context.current()
        name = getattr(ctx.route, "route_name", None) if ctx is not None else None
        return {"route": name}

    async def dashboard(self):
        return {"ok": True}

    async def show(self, id: int):
        return {"id": id}

    async def store(self):
        return {"stored": True}
