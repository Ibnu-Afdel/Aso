from __future__ import annotations

from fastogram.http import Controller, Request

from app.http.requests.store_post_request import StorePostRequest


class PostController(Controller):
    async def index(self, request: Request) -> dict:
        page = request.query("page")
        return {"page": page}

    async def store(self, data: StorePostRequest) -> dict:
        return {"title": data.title}
