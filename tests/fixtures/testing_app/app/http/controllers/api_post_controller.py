from __future__ import annotations

from fastogram.http import Controller

from app.http.requests.store_post_request import StorePostRequest
from app.models.post import Post


class ApiPostController(Controller):
    async def index(self) -> dict:
        posts = await Post.order_by(Post.id).get()
        return {"data": [{"id": p.id, "title": p.title} for p in posts], "status": "ok"}

    async def store(self, form: StorePostRequest) -> dict:
        post = await Post.create(title=form.title, body=form.body, user_id=None)
        return {"id": post.id, "title": post.title}

    async def show(self, post: Post) -> dict:
        return {"id": post.id, "title": post.title}
