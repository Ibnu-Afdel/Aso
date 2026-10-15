"""Database inspection/utility commands (T-30): `db`, `db:show`, `db:table`, `db:wipe`."""

from __future__ import annotations

import os
from typing import Any

from fastogram.console.command import Command
from fastogram.console.registry import register
from fastogram.console.support import guard_production


def _connection() -> dict[str, Any]:
    from fastogram.config import config

    name = config("database.default")
    return config(f"database.connections.{name}") or {}


async def _run_sync(fn: Any, *args: Any) -> Any:
    from fastogram.database.engine import engine

    async with engine().connect() as conn:
        return await conn.run_sync(fn, *args)


class DbCommand(Command):
    signature = "db {--read : Connect to a read replica (reserved, unused in v1)}"
    description = "Start a new database CLI session"

    async def handle(self) -> int:
        from fastogram.database.engine import engine

        dialect = engine().dialect.name
        connection = _connection()
        argv = _client_argv(dialect, connection)
        if argv is None:
            self.error(f'No database client is known for dialect "{dialect}".')
            return 1
        self.info(f"Connecting to the {dialect} database...")
        import subprocess

        return subprocess.call(argv)


def _client_argv(dialect: str, connection: dict[str, Any]) -> list[str] | None:
    if dialect == "sqlite":
        from fastogram.foundation.paths import base_path

        database = str(connection.get("database") or "database/database.sqlite")
        path = base_path(database) if not os.path.isabs(database) else database
        return ["sqlite3", str(path)]
    if dialect == "postgresql":
        argv = ["psql"]
        if connection.get("host"):
            argv += ["-h", str(connection["host"])]
        if connection.get("port"):
            argv += ["-p", str(connection["port"])]
        if connection.get("username"):
            argv += ["-U", str(connection["username"])]
        argv += [str(connection.get("database", ""))]
        return argv
    if dialect in ("mysql", "mariadb"):
        argv = ["mysql"]
        if connection.get("host"):
            argv += ["-h", str(connection["host"])]
        if connection.get("port"):
            argv += ["-P", str(connection["port"])]
        if connection.get("username"):
            argv += ["-u", str(connection["username"])]
        argv += [str(connection.get("database", ""))]
        return argv
    return None


class DbShowCommand(Command):
    signature = "db:show"
    description = "Display information about the current database connection"

    async def handle(self) -> int:
        from fastogram.database.engine import engine

        dialect = engine().dialect.name
        connection = _connection()

        def _tables(sync_conn: Any) -> list[str]:
            from sqlalchemy import inspect as sa_inspect

            return sa_inspect(sync_conn).get_table_names()

        tables = await _run_sync(_tables)
        rows = [
            ["Connection", connection.get("driver", dialect)],
            ["Database", connection.get("database") or connection.get("url") or ""],
            ["Tables", str(len(tables))],
        ]
        if dialect == "sqlite":
            from fastogram.foundation.paths import base_path

            database = connection.get("database")
            if database and database != ":memory:":
                path = base_path(database) if not os.path.isabs(str(database)) else database
                try:
                    rows.append(["Size", f"{os.path.getsize(path)} bytes"])
                except OSError:
                    pass
        self.table(["Property", "Value"], rows)
        if tables:
            self.new_line()
            self.table(["Table"], [[t] for t in tables])
        return 0


class DbTableCommand(Command):
    signature = "db:table {table : The table to describe}"
    description = "Display information about a database table"

    async def handle(self) -> int:
        table_name = self.argument("table")

        def _describe(sync_conn: Any) -> dict[str, Any]:
            from sqlalchemy import inspect as sa_inspect

            inspector = sa_inspect(sync_conn)
            if table_name not in inspector.get_table_names():
                return {}
            return {
                "columns": inspector.get_columns(table_name),
                "indexes": inspector.get_indexes(table_name),
                "foreign_keys": inspector.get_foreign_keys(table_name),
            }

        info = await _run_sync(_describe)
        if not info:
            self.error(f'Table "{table_name}" does not exist.')
            return 1
        self.table(
            ["Column", "Type", "Nullable"],
            [[c["name"], str(c["type"]), "YES" if c.get("nullable", True) else "NO"] for c in info["columns"]],
        )
        if info["indexes"]:
            self.new_line()
            self.table(["Index", "Columns", "Unique"], [[i["name"], ", ".join(i["column_names"]), str(i["unique"])] for i in info["indexes"]])
        if info["foreign_keys"]:
            self.new_line()
            self.table(
                ["Column(s)", "References"],
                [[", ".join(fk["constrained_columns"]), f"{fk['referred_table']}({', '.join(fk['referred_columns'])})"] for fk in info["foreign_keys"]],
            )
        return 0


class DbWipeCommand(Command):
    signature = "db:wipe {--force : Force the operation to run in production}"
    description = "Drop all tables"

    async def handle(self) -> int:
        if not await guard_production(self, action="drop all tables"):
            return 1
        from fastogram.console.migrations import drop_all_tables

        await drop_all_tables()
        self.info("Database wiped successfully.")
        return 0


def register_all() -> None:
    for cls in (DbCommand, DbShowCommand, DbTableCommand, DbWipeCommand):
        register(cls, source="framework")
