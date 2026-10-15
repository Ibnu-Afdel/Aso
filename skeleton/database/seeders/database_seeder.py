"""The entry point for `fastogram db:seed` (T-36). Call your own seeders from `run()`."""

from fastogram.database import Seeder


class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        await self.call([])
