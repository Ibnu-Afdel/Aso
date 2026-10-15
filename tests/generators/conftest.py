"""Fixtures for `tests/generators/` (T-51): the same booted-project pattern as
`tests/console/conftest.py`, reusing `tests/fixtures/console_app` so generated files land next to
a real `app/models/post.py` and a real `bootstrap/app.py`. Each test gets a fresh temp SQLite
database and starts with an empty `database/migrations/`; anything a test generates under
`app/`, `database/`, `resources/`, `stubs/`, or `tests/feature|unit/` inside the fixture app is
cleaned up afterwards so generator tests never leak into each other or into `tests/console/`."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

CONSOLE_APP = Path(__file__).parent.parent / "fixtures" / "console_app"

_GENERATED_DIRS = (
    "stubs",
    "tests",
)
# Files/directories created by generators, relative to the app root, removed after each test --
# anything already present before the test (the fixture's own `app/models/post.py`, etc.) is
# tracked and preserved by snapshotting the generated-code roots instead of deleting them wholesale.
_GENERATED_ROOTS = (
    "app/http/controllers",
    "app/http/requests",
    "app/http/middleware",
    "app/models",
    "app/policies",
    "app/jobs",
    "app/events",
    "app/listeners",
    "app/mail",
    "app/console/commands",
    "database/factories",
    "database/seeders",
    "resources/js/pages",
    "resources/views/mail",
)


def _snapshot() -> dict[str, set[str]]:
    snapshot: dict[str, set[str]] = {}
    for rel in _GENERATED_ROOTS:
        directory = CONSOLE_APP / rel
        snapshot[rel] = {str(p) for p in directory.rglob("*")} if directory.is_dir() else set()
    return snapshot


def _restore(snapshot: dict[str, set[str]]) -> None:
    for rel in _GENERATED_ROOTS:
        directory = CONSOLE_APP / rel
        if not directory.is_dir():
            continue
        before = snapshot[rel]
        for path in sorted(directory.rglob("*"), reverse=True):
            if str(path) not in before and path.exists():
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path, ignore_errors=True)
    for rel in _GENERATED_DIRS:
        shutil.rmtree(CONSOLE_APP / rel, ignore_errors=True)


@pytest.fixture
def console_app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DB_DATABASE", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("FASTOGRAM_NO_HANDOVER", "1")
    migrations_dir = CONSOLE_APP / "database" / "migrations"
    shutil.rmtree(migrations_dir, ignore_errors=True)
    before = _snapshot()
    try:
        yield CONSOLE_APP
    finally:
        shutil.rmtree(migrations_dir, ignore_errors=True)
        _restore(before)
        env_path = CONSOLE_APP / ".env"
        if env_path.exists():
            env_path.unlink()


@pytest.fixture
def cli_group(console_app_dir: Path):
    from fastogram.console.cli import build_cli

    return build_cli(console_app_dir)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FASTOGRAM_HANDED_OVER", raising=False)
    yield
