"""Shared fixtures for `tests/console/`: a tiny booted project (`tests/fixtures/console_app`)
with an isolated temp SQLite database and migrations directory per test."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

CONSOLE_APP = Path(__file__).parent.parent / "fixtures" / "console_app"


@pytest.fixture
def console_app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`tests/fixtures/console_app`, pointed at a fresh temp SQLite file and an empty
    `database/migrations/` (removed again afterwards -- migration files are test output, not
    fixture content)."""
    monkeypatch.setenv("DB_DATABASE", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("ASO_NO_HANDOVER", "1")
    migrations_dir = CONSOLE_APP / "database" / "migrations"
    shutil.rmtree(migrations_dir, ignore_errors=True)
    try:
        yield CONSOLE_APP
    finally:
        shutil.rmtree(migrations_dir, ignore_errors=True)
        env_path = CONSOLE_APP / ".env"
        if env_path.exists():
            env_path.unlink()


@pytest.fixture
def cli_group(console_app_dir: Path):
    """A fully built CLI (`build_cli`) booted against `console_app_dir`."""
    from aso.console.cli import build_cli

    return build_cli(console_app_dir)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    # Never let one test's hand-over marker leak into the next.
    monkeypatch.delenv("ASO_HANDED_OVER", raising=False)
    yield
