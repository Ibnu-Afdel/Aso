"""T-55: end-to-end test of `fastogram.testing.plugin` itself, run the way a real app's test
suite would run it -- a separate `pytest` subprocess, inside a tiny fixture project
(`tests/fixtures/plugin_project/`) that has no `database/migrations/` directory (exercising the
`Model.metadata.create_all` fallback) and relies on the `pytest11` entry point to autoload the
plugin (nothing in that project disables it with `-p no:fastogram`, unlike this repo's own
`pyproject.toml`).

These are `async def` tests only so `tests/testing/conftest.py`'s autouse `db` fixture (async)
can attach to them like every other test in this directory (pytest-asyncio has no way to run an
async fixture for a *sync* test); neither test actually uses the `db`/`app` it pulls in -- they
only shell out to a separate `pytest` process and check its exit code and output.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.parent / "fixtures" / "plugin_project"


async def test_plugin_fixtures_pass_in_a_real_app_s_own_test_suite() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"The plugin_project fixture suite failed:\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    assert "4 passed" in result.stdout, result.stdout


async def test_plugin_autoloads_via_the_pytest11_entry_point_without_pytest_plugins() -> None:
    """No `conftest.py` and no `pytest_plugins = [...]` live in `plugin_project/` -- the `app`/
    `client`/autouse `db` fixtures must come purely from the `pyproject.toml` entry point."""
    assert not (PROJECT / "conftest.py").exists()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only"],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 tests collected" in result.stdout or "4/4 tests collected" in result.stdout
