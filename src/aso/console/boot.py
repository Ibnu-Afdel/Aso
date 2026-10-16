"""Project detection, booting, and the global-installer-vs-project hand-over (D-014, T-02)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

NO_HANDOVER_ENV = "ASO_NO_HANDOVER"
HANDED_OVER_ENV = "ASO_HANDED_OVER"


def find_project_root(start: Path | None = None) -> Path | None:
    """`cwd` or the nearest parent containing `bootstrap/app.py`."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "bootstrap" / "app.py").is_file():
            return candidate
    return None


def hand_over_target(project_root: Path) -> Path | None:
    """The project's own `.venv/bin/aso`, or `None` when we are already running it (or
    hand-over is disabled, e.g. in tests via `ASO_NO_HANDOVER=1`)."""
    if os.environ.get(NO_HANDOVER_ENV) or os.environ.get(HANDED_OVER_ENV):
        return None
    target = project_root / ".venv" / "bin" / "aso"
    if not target.is_file():
        return None
    this = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    try:
        if this is not None and this.samefile(target):
            return None
    except OSError:
        if this is not None and this == target.resolve():
            return None
    return target


def boot_console(project_root: Path) -> None:
    """Import the project's `bootstrap/app.py` and call `create_app()`, then discover user
    commands (same import style as the test client fixtures: `sys.path` + a plain import, so a
    project behaves exactly as it would under `uvicorn bootstrap.app:create_app --factory`).

    `project_root` is put on `sys.path` and left there -- a real CLI invocation is a one-shot
    process, and tests that boot more than one fixture app per process manage `sys.path` /
    `sys.modules` isolation themselves (see `tests/conftest.py`'s `reset_fixture_apps()`)."""
    import importlib

    from aso.console.commands import register_framework_commands
    from aso.console.registry import discover_user_commands, load_console_routes, reset_registry

    register_framework_commands()

    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)

    _dispose_previous_engine()

    already_imported = "bootstrap.app" in sys.modules
    import bootstrap.app as bootstrap_app

    if already_imported:
        importlib.reload(bootstrap_app)
    bootstrap_app.create_app()

    reset_registry()  # drop a previous boot's user commands before re-discovering them
    discover_user_commands(project_root)
    load_console_routes(project_root)


def _dispose_previous_engine() -> None:
    """Every `aso queue:work`/`route:list`/... invocation re-runs `create_app()` fresh via
    `asyncio.run()` (T-50: "a fresh request-less context"); without disposing the previous
    engine first, each boot leaves its predecessor's connection pool (and, with SQLite, its
    `aiosqlite` worker thread) dangling once its event loop has closed. A one-shot CLI process
    only ever boots once, so this matters for tests, which boot the same or different fixture
    apps many times in one process."""
    import asyncio

    from aso.database import engine as engine_module

    try:
        current = engine_module.engine()
    except RuntimeError:
        return
    asyncio.run(current.dispose())
