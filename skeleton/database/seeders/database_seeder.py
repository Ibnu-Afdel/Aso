"""The entry point for `aso db:seed` (T-36). Call your own seeders from `run()`."""

from aso.database import Seeder


class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        await self.call([])
