"""Migration commands (T-35): `make:migration`, `migrate`, `migrate:rollback`, `migrate:reset`,
`migrate:refresh`, `migrate:fresh`, `migrate:status`."""

from __future__ import annotations

from aso.console import migrations
from aso.console.command import Command
from aso.console.registry import register
from aso.console.support import guard_production


def _base_path():
    from aso.foundation.paths import base_path

    return base_path()


class MakeMigrationCommand(Command):
    signature = 'make:migration {name : A short description, e.g. "create posts table"} {--empty : Create a blank migration}'
    description = "Create a new migration file"

    async def handle(self) -> int:
        name = self.argument("name")
        path = await migrations.make_migration(name, empty=bool(self.option("empty")), base_path=_base_path())
        self.info(f"Created migration: {path.relative_to(_base_path())}")
        return 0


class MigrateCommand(Command):
    signature = (
        "migrate {--force : Force the operation to run in production} {--pretend : Only output the SQL} "
        "{--seed : Seed the database after migrating}"
    )
    description = "Run the database migrations"

    async def handle(self) -> int:
        if not await guard_production(self, action="run the migrations"):
            return 1
        lines = await migrations.migrate(pretend=bool(self.option("pretend")))
        if self.option("pretend"):
            for line in lines:
                self.line(line)
        else:
            self.info("Migration table migrated successfully.")
        if self.option("seed") and not self.option("pretend"):
            exit_code = await self.call("db:seed")
            if exit_code != 0:
                return exit_code
        return 0


class MigrateRollbackCommand(Command):
    signature = (
        "migrate:rollback {--step=1 : The number of migrations to roll back} "
        "{--force : Force the operation to run in production} {--pretend : Only output the SQL}"
    )
    description = "Rollback the last database migration"

    async def handle(self) -> int:
        if not await guard_production(self, action="roll back the migrations"):
            return 1
        step = int(self.option("step") or 1)
        lines = await migrations.rollback(step=step, pretend=bool(self.option("pretend")))
        if self.option("pretend"):
            for line in lines:
                self.line(line)
        else:
            self.info("Rollback successful.")
        return 0


class MigrateResetCommand(Command):
    signature = "migrate:reset {--force : Force the operation to run in production}"
    description = "Rollback all database migrations"

    async def handle(self) -> int:
        if not await guard_production(self, action="reset the database"):
            return 1
        await migrations.reset()
        self.info("Database reset successfully.")
        return 0


class MigrateRefreshCommand(Command):
    signature = "migrate:refresh {--force : Force the operation to run in production}"
    description = "Reset and re-run all migrations"

    async def handle(self) -> int:
        if not await guard_production(self, action="refresh the database"):
            return 1
        await migrations.refresh()
        self.info("Database refreshed successfully.")
        return 0


class MigrateFreshCommand(Command):
    signature = "migrate:fresh {--force : Force the operation to run in production} {--seed : Seed the database after migrating}"
    description = "Drop all tables and re-run all migrations"

    async def handle(self) -> int:
        if not await guard_production(self, action="drop all tables"):
            return 1
        await migrations.fresh(base_path=_base_path())
        self.info("Database refreshed successfully.")
        if self.option("seed"):
            exit_code = await self.call("db:seed")
            if exit_code != 0:
                return exit_code
        return 0


class MigrateStatusCommand(Command):
    signature = "migrate:status"
    description = "Show the status of each migration"

    async def handle(self) -> int:
        rows = await migrations.status()
        if not rows:
            self.info("No migrations found.")
            return 0
        self.table(
            ["Status", "Migration"],
            [["Ran" if r.applied else "Pending", f"{r.revision}  {r.message}".strip()] for r in rows],
        )
        return 0


def register_all() -> None:
    for cls in (
        MakeMigrationCommand,
        MigrateCommand,
        MigrateRollbackCommand,
        MigrateResetCommand,
        MigrateRefreshCommand,
        MigrateFreshCommand,
        MigrateStatusCommand,
    ):
        register(cls, source="framework")
