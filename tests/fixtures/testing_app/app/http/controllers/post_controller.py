from __future__ import annotations

from fastogram.auth import auth
from fastogram.http import Controller, redirect
from fastogram.inertia import defer, inertia, merge, once

from app.http.requests.store_post_request import StorePostRequest
from app.models.post import Post


class PostController(Controller):
    async def index(self) -> object:
        posts = await Post.order_by(Post.id).get()
        return inertia(
            "posts/index",
            {
                "posts": {
                    "data": [{"id": p.id, "title": p.title, "user_id": p.user_id} for p in posts],
                    "total": len(posts),
                },
                "notifications": merge(lambda: ["welcome"]),
                "stats": once(lambda: {"count": len(posts)}),
                "sidebar": defer(lambda: ["tag-a", "tag-b"]),
            },
        )

    async def create(self) -> object:
        return inertia("posts/create")

    async def store(self, form: StorePostRequest) -> object:
        user = auth().user()
        await Post.create(title=form.title, body=form.body, user_id=user.id if user else None)
        return redirect().route("posts.index").with_flash("success", "Post created.")

    async def show(self, post: Post) -> object:
        return inertia("posts/show", {"post": {"id": post.id, "title": post.title}})
