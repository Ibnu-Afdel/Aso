from __future__ import annotations

from fastogram.http import Controller

from app.models.post import Post


class PostController(Controller):
    async def show(self, post: Post) -> dict:
        return {"id": post.id, "title": post.title}

    async def edit(self, post: Post) -> dict:
        return {"id": post.id, "title": post.title, "editing": True}
