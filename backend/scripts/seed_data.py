import asyncio

from app.core.db import async_session_maker
from app.modules.users.repository import UserRepository


async def main() -> None:
    async with async_session_maker() as session:
        repo = UserRepository(session)
        await repo.create(telegram_id=123456789)


if __name__ == "__main__":
    asyncio.run(main())
