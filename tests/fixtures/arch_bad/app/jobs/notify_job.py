from __future__ import annotations

from aso.queue import Job

from app.models.post import Post


class NotifyJob(Job):
    def __init__(self, post: Post) -> None:
        self.post = post

    async def handle(self) -> None:
        pass
