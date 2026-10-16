from __future__ import annotations

from aso.auth import auth
from aso.http import Controller
from aso.inertia import inertia

from app.models.post import Post


class PostController(Controller):
    async def index(self) -> object:
        posts = await Post.order_by(Post.id).get()
        return inertia(
            "posts/index",
            {
                "posts": [{"id": p.id, "title": p.title} for p in posts],
                "me": auth().id(),
            },
        )

    async def store(self) -> dict:
        post = await Post.create(title="A post")
        return {"id": post.id}
