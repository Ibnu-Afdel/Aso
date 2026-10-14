from __future__ import annotations

from fastogram.http import Controller


class PingController(Controller):
    async def index(self) -> dict:
        return {"ok": True}

    async def named(self) -> dict:
        return {"ok": True}

    async def unlimited(self) -> dict:
        return {"ok": True}
