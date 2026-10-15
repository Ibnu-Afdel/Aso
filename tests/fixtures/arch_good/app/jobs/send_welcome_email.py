from __future__ import annotations

from fastogram.queue import Job


class SendWelcomeEmail(Job):
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    async def handle(self) -> None:
        pass
