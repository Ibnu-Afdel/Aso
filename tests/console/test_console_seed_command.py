"""`db:seed` (T-36) and `migrate`/`migrate:fresh --seed`'s hook into it, against the
`console_app` fixture (which already has a `Post` model, T-31)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def seeders_dir(console_app_dir: Path):
    directory = console_app_dir / "database" / "seeders"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").touch()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _write_database_seeder(directory: Path, body: str) -> None:
    (directory / "database_seeder.py").write_text(body)


def test_db_seed_runs_the_database_seeder(cli_group, runner: CliRunner, console_app_dir: Path, seeders_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    runner.invoke(cli_group, ["migrate"])

    _write_database_seeder(
        seeders_dir,
        "from app.models.post import Post\n"
        "from aso.database import Seeder\n\n"
        "class DatabaseSeeder(Seeder):\n"
        "    async def run(self) -> None:\n"
        "        await Post.create(title='Seeded', body='x')\n",
    )

    result = runner.invoke(cli_group, ["db:seed"])
    assert result.exit_code == 0, result.output
    assert "Database seeded" in result.output

    show = runner.invoke(cli_group, ["db:table", "posts"])
    assert "title" in show.output


def test_db_seed_class_option_runs_a_specific_seeder(cli_group, runner: CliRunner, console_app_dir: Path, seeders_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    runner.invoke(cli_group, ["migrate"])

    (seeders_dir / "post_seeder.py").write_text(
        "from app.models.post import Post\n"
        "from aso.database import Seeder\n\n"
        "class PostSeeder(Seeder):\n"
        "    async def run(self) -> None:\n"
        "        await Post.create(title='FromClassOption', body='x')\n"
    )

    result = runner.invoke(cli_group, ["db:seed", "--class=PostSeeder"])
    assert result.exit_code == 0, result.output
    assert "PostSeeder" in result.output


def test_db_seed_missing_seeder_reports_an_error(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["db:seed"])
    assert result.exit_code == 1
    assert "DatabaseSeeder" in result.output


def test_migrate_fresh_seed_runs_the_seeder(cli_group, runner: CliRunner, console_app_dir: Path, seeders_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    runner.invoke(cli_group, ["migrate"])

    _write_database_seeder(
        seeders_dir,
        "from app.models.post import Post\n"
        "from aso.database import Seeder\n\n"
        "class DatabaseSeeder(Seeder):\n"
        "    async def run(self) -> None:\n"
        "        await Post.create(title='FreshSeeded', body='x')\n",
    )

    result = runner.invoke(cli_group, ["migrate:fresh", "--seed"])
    assert result.exit_code == 0, result.output

    show = runner.invoke(cli_group, ["db:table", "posts"])
    assert "title" in show.output


def test_migrate_seed_runs_the_seeder(cli_group, runner: CliRunner, console_app_dir: Path, seeders_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])

    _write_database_seeder(
        seeders_dir,
        "from app.models.post import Post\n"
        "from aso.database import Seeder\n\n"
        "class DatabaseSeeder(Seeder):\n"
        "    async def run(self) -> None:\n"
        "        await Post.create(title='MigrateSeeded', body='x')\n",
    )

    result = runner.invoke(cli_group, ["migrate", "--seed"])
    assert result.exit_code == 0, result.output

    show = runner.invoke(cli_group, ["db:table", "posts"])
    assert "title" in show.output
