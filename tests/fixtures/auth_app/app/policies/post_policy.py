from __future__ import annotations

from app.models.post import Post
from app.models.user import User


class PostPolicy:
    async def view(self, user: User | None, post: Post) -> bool:
        return True

    async def update(self, user: User, post: Post) -> bool:
        return user.id == post.user_id
