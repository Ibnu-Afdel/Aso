"""Alembic wiring (T-35): a fully programmatic environment.

Aso never writes (or needs) an `alembic.ini` or `env.py` in the app. `database/migrations/`
holds revision files directly (Alembic's `versions/` subdirectory convention is not used, so
`ScriptDirectory` is pointed at `database/migrations/` itself via `version_locations`). Applying
migrations replicates Alembic's asyncio recipe (`EnvironmentContext` + `MigrationContext`,
driven from this module instead of a generated `env.py` file) so SQLAlchemy's async engine can
run the (synchronous) Alembic machinery through `AsyncConnection.run_sync()`.

SQLite runs every migration in batch mode (`render_as_batch=True`); `compare_type=True` is
always on for autogenerate. PostgreSQL and SQLite DDL is transactional; MySQL is not (T-35).
"""

from __future__ import annotations

import importlib.util
import io
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from alembic import util as alembic_util
from alembic.autogenerate import produce_migrations, render_python_code
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

__all__ = [
    "MigrationStatus",
    "drop_all_tables",
    "fresh",
    "import_app_models",
    "make_migration",
    "migrate",
    "migrations_dir",
    "new_revision_id",
    "refresh",
    "render_skeleton_migration",
    "reset",
    "rollback",
    "status",
]


def migrations_dir() -> Path:
    from aso.foundation.paths import database_path

    return database_path("migrations")


def import_app_models(base_path: Path) -> None:
    """Import every module in `app/models/` so `Model.metadata` is complete before comparing it
    against the live schema (T-35; pivot tables declared by `belongs_to_many` come along, T-33)."""
    directory = base_path / "app" / "models"
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"app.models.{path.stem}"
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)


def _config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(migrations_dir()))
    return config


def _script_directory() -> ScriptDirectory:
    directory = migrations_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return ScriptDirectory(str(directory), version_locations=[str(directory)], truncate_slug_length=255)


async def _is_sqlite() -> bool:
    from aso.database.engine import engine

    return engine().dialect.name == "sqlite"


async def _with_sync_connection(fn: Any, *args: Any) -> Any:
    from aso.database.engine import engine

    async with engine().connect() as conn:
        return await conn.run_sync(fn, *args)


# ---------------------------------------------------------------- make:migration


def _render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Render our `TypeDecorator` columns (`UtcDateTime`, `Encrypted`, `Hashed`, T-31/T-40) as
    their underlying plain SQLAlchemy type, matching the guide's own migration examples (plain
    `sa.DateTime(timezone=True)`, not a dotted `aso.database.types.UtcDateTime` the
    generated file never imports)."""
    if type_ == "type":
        from sqlalchemy.types import TypeDecorator

        if isinstance(obj, TypeDecorator):
            from alembic.autogenerate.render import _repr_type

            return _repr_type(obj.impl, autogen_context)
    return False


def _slug(message: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", message.strip().lower()).strip("_")
    return slug or "migration"


_FILE_TEMPLATE = '''"""{message}

Revision ID: {revision}
Revises: {down_revision}
Create Date: {create_date}
"""

from alembic import op
import sqlalchemy as sa

revision = {revision!r}
down_revision = {down_revision!r}
branch_labels = None
depends_on = None


def upgrade() -> None:
{upgrade_body}


def downgrade() -> None:
{downgrade_body}
'''


async def make_migration(message: str, *, empty: bool = False, base_path: Path | None = None) -> Path:
    """`aso make:migration "create posts table"` (T-35): autogenerate a revision by
    comparing `Model.metadata` against the live schema, or `--empty` for a blank stub."""
    if base_path is not None and not empty:
        import_app_models(base_path)
    script = _script_directory()
    head = script.get_current_head()

    if empty:
        upgrade_body, downgrade_body = "    pass", "    pass"
    else:
        from aso.database import Model

        render_as_batch = await _is_sqlite()

        def _produce(sync_conn: Any) -> Any:
            migration_context = MigrationContext.configure(
                connection=sync_conn,
                opts={"compare_type": True, "render_as_batch": render_as_batch, "target_metadata": Model.metadata},
            )
            return produce_migrations(migration_context, Model.metadata)

        migration_script = await _with_sync_connection(_produce)
        upgrade_body = render_python_code(migration_script.upgrade_ops, render_as_batch=render_as_batch, render_item=_render_item) or "    pass"
        downgrade_body = render_python_code(migration_script.downgrade_ops, render_as_batch=render_as_batch, render_item=_render_item) or "    pass"

    revision = alembic_util.rev_id()
    now = datetime.now()
    filename = f"{now.strftime('%Y_%m_%d_%H%M%S')}_{_slug(message)}.py"
    path = migrations_dir() / filename
    path.write_text(
        _FILE_TEMPLATE.format(
            message=message,
            revision=revision,
            down_revision=head,
            create_date=now.isoformat(sep=" ", timespec="seconds"),
            upgrade_body=upgrade_body,
            downgrade_body=downgrade_body,
        )
    )
    return path


# ---------------------------------------------------------------- applying migrations


async def _current_heads() -> tuple[str, ...]:
    def _read(sync_conn: Any) -> tuple[str, ...]:
        return MigrationContext.configure(connection=sync_conn).get_current_heads()

    return await _with_sync_connection(_read)


async def _run_steps(fn: Any, destination_rev: str, *, pretend: bool) -> list[str]:
    """Drive Alembic's migration runner directly (no `env.py` on disk, see module docstring)."""
    script = _script_directory()
    config = _config()
    render_as_batch = await _is_sqlite()
    buffer = io.StringIO()
    env_ctx = EnvironmentContext(config, script, fn=fn, destination_rev=destination_rev, as_sql=pretend)

    def do_run_migrations(sync_conn: Any) -> None:
        kwargs: dict[str, Any] = {"connection": sync_conn, "render_as_batch": render_as_batch, "compare_type": True}
        if pretend:
            kwargs.update(as_sql=True, output_buffer=buffer, literal_binds=True)
        env_ctx.configure(**kwargs)
        with env_ctx.begin_transaction():
            env_ctx.run_migrations()

    with env_ctx:
        await _with_sync_connection(do_run_migrations)
    return buffer.getvalue().splitlines() if pretend else []


async def migrate(*, pretend: bool = False) -> list[str]:
    """`aso migrate` -> `upgrade head`; `--pretend` -> offline mode (`upgrade head --sql`)."""
    script = _script_directory()

    def fn(rev: Any, _context: Any) -> Any:
        return script._upgrade_revs("head", rev)

    return await _run_steps(fn, "head", pretend=pretend)


async def rollback(*, step: int = 1, pretend: bool = False) -> list[str]:
    """`aso migrate:rollback [--step=N]` -> `downgrade -N`."""
    script = _script_directory()
    target = f"-{max(1, step)}"

    def fn(rev: Any, _context: Any) -> Any:
        return script._downgrade_revs(target, rev)

    return await _run_steps(fn, target, pretend=pretend)


async def reset(*, pretend: bool = False) -> list[str]:
    """`aso migrate:reset` -> `downgrade base` (every migration rolled back)."""
    script = _script_directory()

    def fn(rev: Any, _context: Any) -> Any:
        return script._downgrade_revs("base", rev)

    return await _run_steps(fn, "base", pretend=pretend)


async def refresh() -> None:
    """`aso migrate:refresh`: roll back every migration, then re-apply them all."""
    await reset()
    await migrate()


async def fresh(*, base_path: Path | None = None) -> None:
    """`aso migrate:fresh`: drop every table (reflected, not just migrated ones), then
    `migrate` (T-35 "How it works" #5)."""
    await drop_all_tables()
    if base_path is not None:
        import_app_models(base_path)
    await migrate()


async def drop_all_tables() -> None:
    """Reflect and drop every table (T-35 `migrate:fresh`/`db:wipe`). Unlike the Alembic-driven
    functions above (whose `begin_transaction()` commits on the DBAPI connection directly), this
    is plain SQLAlchemy Core DDL through the async engine's "begin once" connection, which needs
    an explicit commit -- without it, the drop is rolled back when the connection is released."""
    from aso.database.engine import engine

    def _drop(sync_conn: Any) -> None:
        from sqlalchemy import MetaData

        reflected = MetaData()
        reflected.reflect(bind=sync_conn)
        reflected.drop_all(bind=sync_conn)

    async with engine().connect() as conn:
        await conn.run_sync(_drop)
        await conn.commit()


@dataclass(frozen=True)
class MigrationStatus:
    revision: str
    message: str
    applied: bool


async def status() -> list[MigrationStatus]:
    """`aso migrate:status`: every revision, oldest first, with whether it is applied."""
    script = _script_directory()
    revisions = {s.revision: s for s in script.walk_revisions()}
    heads = await _current_heads()

    applied: set[str] = set()
    for head in heads:
        node: str | None = head
        while node is not None and node in revisions:
            applied.add(node)
            down = revisions[node].down_revision
            node = down[0] if isinstance(down, tuple) else down

    rows = [MigrationStatus(s.revision, s.doc or "", s.revision in applied) for s in revisions.values()]
    rows.sort(key=lambda r: _revision_order(revisions, r.revision))
    return rows


_SKELETON_TEMPLATE = '''"""create users, password_reset_tokens, sessions and failed_jobs tables

Revision ID: {revision}
Revises:
Create Date: {create_date}
"""

from alembic import op
import sqlalchemy as sa

revision = {revision!r}
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("remember_token", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("email", sa.String(length=255), primary_key=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True, index=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("last_activity", sa.Integer(), nullable=False, index=True),
    )
    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("connection", sa.String(length=255), nullable=False),
        sa.Column("queue", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("exception", sa.Text(), nullable=False),
        sa.Column("failed_at", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("failed_jobs")
    op.drop_table("sessions")
    op.drop_table("password_reset_tokens")
    op.drop_table("users")
'''


def render_skeleton_migration() -> str:
    """The skeleton's first migration (T-35, T-38, T-18, T-42): `users`, `password_reset_tokens`
    (`email` primary key, `token`, `created_at`), `sessions` and `failed_jobs`. For the skeleton
    task: write this to `database/migrations/<timestamp>_create_users_table.py`, with a
    `revision` id from `aso.console.migrations.new_revision_id()`."""
    return _SKELETON_TEMPLATE.format(revision=alembic_util.rev_id(), create_date=datetime.now().isoformat(sep=" ", timespec="seconds"))


def new_revision_id() -> str:
    return alembic_util.rev_id()


def _revision_order(revisions: dict[str, Any], revision: str) -> int:
    """Depth from the root (`down_revision is None`), so `status()` prints oldest first."""
    depth = 0
    node = revisions.get(revision)
    seen: set[str] = set()
    while node is not None and node.down_revision and node.revision not in seen:
        seen.add(node.revision)
        down = node.down_revision[0] if isinstance(node.down_revision, tuple) else node.down_revision
        node = revisions.get(down)
        depth += 1
    return depth
