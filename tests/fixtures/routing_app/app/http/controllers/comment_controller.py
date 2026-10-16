from aso.http import Controller, Request

from app.models.comment import Comment
from app.models.post import Post


class CommentController(Controller):
    """Nested resource `posts.comments` (T-10): the child is loaded scoped through the parent."""

    async def index(self, post: Post):
        return {"post_id": post.id, "comments": [c.only("id", "body") for c in await Comment.where(Comment.post_id == post.id).get()]}

    async def create(self, post: Post):
        return {"post_id": post.id}

    async def store(self, post: Post, request: Request):
        body = await request.input("body")
        comment = await Comment.create(post_id=post.id, body=body)
        return comment.only("id", "body", "post_id")

    async def show(self, post: Post, comment: Comment):
        return {"post_id": post.id, "comment": comment.only("id", "body")}

    async def edit(self, post: Post, comment: Comment):
        return {"post_id": post.id, "comment": comment.only("id", "body")}

    async def update(self, post: Post, comment: Comment, request: Request):
        body = await request.input("body")
        await comment.update(body=body)
        return comment.only("id", "body")

    async def destroy(self, post: Post, comment: Comment):
        await comment.delete()
        return {"deleted": True}
