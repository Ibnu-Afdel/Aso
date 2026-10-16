"""Migrations end to end (T-35): `make:migration` (autogenerate) -> `migrate` -> `migrate:status`
-> `migrate:rollback` -> `migrate:fresh`, against a throwaway SQLite file (T-35's own testing
note: DDL is not rolled back on every database, so this never runs inside the per-test
transaction -- each test gets its own temp file via `console_app_dir`)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner


def test_make_migration_autogenerates_from_models(console_app_dir: Path, cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["make:migration", "create posts table"])
    assert result.exit_code == 0, result.output

    migrations_dir = console_app_dir / "database" / "migrations"
    files = list(migrations_dir.glob("*.py"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "op.create_table('posts'" in content
    assert "sa.Column('title'" in content
    assert "revision = " in content
    assert "down_revision = None" in content
    # Custom TypeDecorator columns render as their plain SQLAlchemy type, not a dotted import
    # the file never adds (T-31's `UtcDateTime` on `created_at`/`updated_at`):
    assert "aso" not in content
    assert "sa.DateTime(timezone=True)" in content


def test_make_migration_empty_is_a_blank_stub(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:migration", "noop", "--empty"])
    assert result.exit_code == 0, result.output
    files = list((console_app_dir / "database" / "migrations").glob("*.py"))
    content = files[0].read_text()
    assert "def upgrade() -> None:\n    pass" in content
    assert "def downgrade() -> None:\n    pass" in content


def test_full_migration_cycle(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    def run(*args: str) -> CliRunner:
        result = runner.invoke(cli_group, list(args))
        assert result.exit_code == 0, (args, result.output, result.exception)
        return result

    run("make:migration", "create posts table")

    status = run("migrate:status")
    assert "Pending" in status.output

    run("migrate")
    status = run("migrate:status")
    assert "Ran" in status.output
    assert "Pending" not in status.output

    show = run("db:show")
    assert "posts" in show.output

    table = run("db:table", "posts")
    assert "title" in table.output

    run("migrate:rollback")
    status = run("migrate:status")
    assert "Pending" in status.output

    run("migrate")
    run("migrate:fresh")
    status = run("migrate:status")
    assert "Ran" in status.output


def test_migrate_pretend_does_not_touch_the_database(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    result = runner.invoke(cli_group, ["migrate", "--pretend"])
    assert result.exit_code == 0
    assert "CREATE TABLE" in result.output

    status = runner.invoke(cli_group, ["migrate:status"])
    assert "Pending" in status.output  # --pretend never applied anything


def test_db_table_reports_missing_table(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["db:table", "no_such_table"])
    assert result.exit_code == 1
    assert "does not exist" in result.output
