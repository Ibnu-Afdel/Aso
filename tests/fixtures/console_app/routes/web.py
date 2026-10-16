from aso.routing import Route


async def _welcome():
    return {"ok": True}


Route.get("/", _welcome).name("welcome")
