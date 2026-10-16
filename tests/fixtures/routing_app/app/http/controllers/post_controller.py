from aso.http import Controller, redirect

from app.http.requests.store_post_request import StorePostRequest
from app.http.requests.update_post_request import UpdatePostRequest
from app.models.post import Post


class PostController(Controller):
    """The seven resource actions (T-10, T-13), registered with `Route.resource("posts", ...)`."""

    async def index(self):
        return {"posts": [p.only("id", "title", "slug") for p in await Post.all()]}

    async def create(self):
        return {"page": "posts/create"}

    async def store(self, form: StorePostRequest):
        post = await Post.create(**form.validated())
        return redirect().route("posts.show", post).with_flash("success", "Post created.")

    async def show(self, post: Post):
        return {"post": post.only("id", "title", "slug")}

    async def show_by_slug(self, post: Post):
        return {"post": post.only("id", "title", "slug")}

    async def edit(self, post: Post):
        return {"post": post.only("id", "title", "slug")}

    async def update(self, form: UpdatePostRequest, post: Post):
        await post.update(**form.validated())
        return redirect().route("posts.show", post).with_flash("success", "Post updated.")

    async def destroy(self, post: Post):
        await post.delete()
        return redirect().route("posts.index").with_flash("success", "Post deleted.")
