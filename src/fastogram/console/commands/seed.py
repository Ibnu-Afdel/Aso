"""`db:seed` (T-36): run database seeders, with the same production guard as `migrate`."""

from __future__ import annotations

from fastogram.console.command import Command
from fastogram.console.registry import register
from fastogram.console.support import guard_production


class DbSeedCommand(Command):
    signature = "db:seed {--class= : The seeder class to run (default: DatabaseSeeder)} {--force : Force the operation to run in production}"
    description = "Seed the database with records"

    async def handle(self) -> int:
        if not await guard_production(self, action="seed the database"):
            return 1
        from fastogram.database.seeder import seed as run_seed

        class_name = self.option("class")
        try:
            await run_seed(class_name)
        except RuntimeError as exc:
            self.error(str(exc))
            return 1
        self.info(f"Database seeded: {class_name or 'DatabaseSeeder'}")
        return 0


def register_all() -> None:
    register(DbSeedCommand, source="framework")
