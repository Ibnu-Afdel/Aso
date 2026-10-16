from aso.http import Controller, ControllerMiddleware


class GatedController(Controller):
    """Controller-declared middleware with `only=` (T-13): `mw_a` wraps `gated`, not `open_action`."""

    @staticmethod
    def middleware() -> list:
        return [ControllerMiddleware("mw_a", only=["gated"])]

    async def gated(self):
        return {"ok": True}

    async def open_action(self):
        return {"ok": True}
