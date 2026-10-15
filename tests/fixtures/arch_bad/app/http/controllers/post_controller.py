from __future__ import annotations

from sqlalchemy import select  # noqa: F401

from fastogram.http import Controller, Request


class PostController(Controller):
    async def index(self, request: Request) -> dict:
        page = request.query("page")
        return {"page": page}
