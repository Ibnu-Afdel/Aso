"""End-to-end proof that `aso new` produces a working app (D-004, D-022, T-02).

Creates an app with `aso new --dev --no-npm` into a temp directory (`--dev` so `uv sync`
resolves `aso` against this repo via a local path source instead of PyPI, and `--no-npm`
so no Node/network is needed), then runs the generated app's own test suite, `route:list` and
`migrate` against it, all in real subprocesses -- exactly what a user would get.

Marked `skeleton` (the slowest tests here, but still well under the three-minute cutoff BUILD.md
allows for excluding a test from the default run) and still part of the default `pytest` run.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skeleton


@pytest.fixture(scope="module")
def generated_app(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from aso.console.commands.new import NewAppOptions, new

    target = tmp_path_factory.mktemp("aso_new") / "demo-app"
    options = NewAppOptions(no_npm=True, dev=True)
    exit_code = asyncio.run(new(str(target), options))
    assert exit_code == 0, f"`aso new` failed for {target}"
    return target


def test_new_app_was_created_with_a_working_venv(generated_app: Path) -> None:
    assert (generated_app / "bootstrap" / "app.py").is_file()
    assert (generated_app / "database" / "database.sqlite").is_file()
    aso_bin = generated_app / ".venv" / "bin" / "aso"
    assert aso_bin.is_file(), "`uv sync` should have installed the project's own `aso` CLI"


def test_new_app_pyproject_was_renamed_and_points_at_this_repo(generated_app: Path) -> None:
    text = (generated_app / "pyproject.toml").read_text()
    assert 'name = "demo-app"' in text
    assert "[tool.uv.sources]" in text  # --dev keeps the editable path source


def test_new_app_route_list_shows_the_auth_kit_routes(generated_app: Path) -> None:
    aso_bin = generated_app / ".venv" / "bin" / "aso"
    result = subprocess.run(
        [str(aso_bin), "route:list"], cwd=generated_app, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dashboard" in result.stdout
    assert "login" in result.stdout


def test_new_app_migrate_is_idempotent(generated_app: Path) -> None:
    aso_bin = generated_app / ".venv" / "bin" / "aso"
    result = subprocess.run(
        [str(aso_bin), "migrate", "--force"], cwd=generated_app, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_new_app_own_test_suite_passes(generated_app: Path) -> None:
    result = subprocess.run(
        ["uv", "run", "pytest", "-q"], cwd=generated_app, capture_output=True, text=True, timeout=180
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "failed" not in result.stdout.lower()
