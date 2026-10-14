from fastogram.http import Controller, redirect
from fastogram.inertia import defer, inertia

from app.http.requests.store_post_request import StorePostRequest
from app.models.post import Post


class PostController(Controller):
    async def index(self):
        return inertia("posts/index", {"posts": defer(lambda: Post.all())})

    async def create(self):
        return inertia("posts/create")

    async def store(self, form: StorePostRequest):
        await Post.create(**form.validated())
        return redirect().route("posts.index").with_flash("success", "Post created.")

    async def stats(self):
        return {"count": await Post.count()}

    async def boom(self):
        raise RuntimeError("boom")

    async def api_show(self, post_id: int):
        post = await Post.find_or_fail(post_id)
        return post.only("id", "title")
