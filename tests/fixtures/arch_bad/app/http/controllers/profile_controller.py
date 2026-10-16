from __future__ import annotations

from aso.http import Controller, Request


class ProfileController(Controller):
    async def update(self, request: Request) -> dict:
        data = await request.json()
        return data
