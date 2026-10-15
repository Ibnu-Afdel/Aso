"""`fastogram new <name>` (T-02, D-004, D-022).

Unlike every other command, `new` runs **outside** a project (there is nothing to boot: no
`bootstrap/app.py`, no database, T-06), so it is not a `Command` subclass driven through the
registry's `run_registered()` (which always opens a `DB.scope()`). It is a plain async function
that `fastogram.console.cli`'s specially-registered `new` typer command calls directly, the same
way `list`/`--version` are special-cased there for the "outside a project" CLI (D-014).

Copies the skeleton that ships inside the `fastogram` package (`fastogram/skeleton/`, falling
back to the repo's own `skeleton/` folder in a dev checkout), renames the app, writes `.env` /
`.env.testing` with fresh `APP_KEY`s, and (unless skipped) runs `uv sync`, `npm install` and
`fastogram migrate`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer

__all__ = ["NewAppOptions", "new"]

_IGNORE_NAMES = shutil.ignore_patterns(
    ".venv", "uv.lock", "node_modules", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", "database.sqlite"
)
# Build output and generated code from a local `npm run build` in the skeleton must never be copied.
_IGNORE_PATHS = {("public", "build"), ("public", "hot"), ("js", "routes"), ("js", "actions"), ("js", "wayfinder")}


def _IGNORE(directory: str, names: list[str]) -> set[str]:  # noqa: N802 - used like shutil.ignore_patterns
    ignored = set(_IGNORE_NAMES(directory, names))
    parent = Path(directory).name
    ignored.update(n for n in names if (parent, n) in _IGNORE_PATHS)
    return ignored

# Must match `skeleton/pyproject.toml` verbatim -- see `_rewrite_pyproject()`.
_DEV_SOURCES_BLOCK = (
    "# Dev checkouts (and `fastogram new --dev`) point this at the framework's own repo, editable.\n"
    "# `fastogram new` (without --dev) removes this table and pins `fastogram` to a released version.\n"
    "[tool.uv.sources]\n"
    'fastogram = { path = "..", editable = true }\n'
)


class NewAppError(RuntimeError):
    pass


@dataclass
class NewAppOptions:
    kit: str = "react"
    database: str = "sqlite"
    no_install: bool = False
    no_npm: bool = False
    no_migrate: bool = False
    git: bool = False
    dev: bool = False
    force: bool = False


# ---------------------------------------------------------------- locating the skeleton


def _package_root() -> Path:
    import fastogram

    return Path(fastogram.__file__).resolve().parent


def _is_dev_repo_root(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "src" / "fastogram").is_dir()


def dev_repo_root() -> Path | None:
    """The `FastGram` repo root, if `fastogram` is running from a dev checkout (editable install
    or `uv run` inside the repo), used both to find the skeleton and to resolve `--dev`'s path
    source."""
    for candidate in (_package_root(), *_package_root().parents):
        if _is_dev_repo_root(candidate):
            return candidate
    return None


def resolve_skeleton_dir() -> Path:
    """`fastogram/skeleton/` inside the installed package; falls back to the repo's own
    `skeleton/` folder in a dev checkout (T-02)."""
    packaged = _package_root() / "skeleton"
    if packaged.is_dir():
        return packaged
    root = dev_repo_root()
    if root is not None and (root / "skeleton").is_dir():
        return root / "skeleton"
    raise NewAppError(
        "Could not find the FastoGram skeleton (expected it packaged at `fastogram/skeleton/`, "
        "or a `skeleton/` folder next to a dev checkout's `src/fastogram/`)."
    )


# ---------------------------------------------------------------- rewriting copied files


def _current_fastogram_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("fastogram")
    except PackageNotFoundError:  # pragma: no cover - only in an unusual, unbuilt dev checkout
        return "0.1.0"


def _rewrite_pyproject(path: Path, *, app_name: str, options: NewAppOptions) -> None:
    text = path.read_text()
    text = re.sub(r'(?m)^name = "app"$', f'name = "{app_name}"', text, count=1)

    if options.dev:
        root = dev_repo_root()
        if root is None:
            raise NewAppError("`--dev` needs a FastoGram dev checkout (no `src/fastogram` was found near the running `fastogram`).")
        dev_block = _DEV_SOURCES_BLOCK.replace('path = ".."', f'path = "{root.as_posix()}"')
        text = text.replace(_DEV_SOURCES_BLOCK, dev_block)
    else:
        text = text.replace(_DEV_SOURCES_BLOCK, "")
        pin = f">={_current_fastogram_version()}"
        text = re.sub(r'(?m)^    "fastogram",$', f'    "fastogram{pin}",', text, count=1)

    path.write_text(text)


def _write_env_file(template: Path, target: Path, *, app_name: str, database: str, app_key: str) -> None:
    text = template.read_text()
    replacements = {"APP_NAME": app_name, "APP_KEY": app_key}
    if "DB_CONNECTION" in text:
        replacements["DB_CONNECTION"] = database
    for key, value in replacements.items():
        pattern = re.compile(rf'(?m)^{key}=.*$')
        line = f"{key}={value}" if " " not in str(value) else f'{key}="{value}"'
        text = pattern.sub(line, text, count=1) if pattern.search(text) else text + f"\n{line}\n"
    target.write_text(text)


# ---------------------------------------------------------------- the command itself


async def new(name: str, options: NewAppOptions | None = None, *, echo=typer.echo) -> int:
    options = options or NewAppOptions()
    if options.kit != "react":
        echo(f'Unknown starter kit "{options.kit}". Only "react" is available in v1.')
        return 1
    if options.database not in ("sqlite", "pgsql", "mysql"):
        echo(f'Unknown database "{options.database}". Choose one of: sqlite, pgsql, mysql.')
        return 1

    target = Path(name).resolve()
    if target.exists():
        if not options.force:
            echo(f"A directory named [{target}] already exists.")
            return 1
        shutil.rmtree(target)

    try:
        skeleton = resolve_skeleton_dir()
    except NewAppError as exc:
        echo(str(exc))
        return 1

    echo(f"Creating a new FastoGram application in {target}...")
    shutil.copytree(skeleton, target, ignore=_IGNORE)

    from fastogram.support import slug

    app_name = name.rstrip("/\\")
    app_name = Path(app_name).name or app_name
    app_slug = slug(app_name)

    _rewrite_pyproject(target / "pyproject.toml", app_name=app_slug, options=options)

    from fastogram.security.keys import generate_key

    _write_env_file(
        skeleton / ".env.example", target / ".env", app_name=app_name, database=options.database, app_key=generate_key()
    )
    _write_env_file(
        skeleton / ".env.testing", target / ".env.testing", app_name=app_name, database="sqlite", app_key=generate_key()
    )

    (target / "database").mkdir(exist_ok=True)
    if options.database == "sqlite":
        (target / "database" / "database.sqlite").touch(exist_ok=True)

    if options.git:
        _run(["git", "init"], target, echo)
        _run(["git", "add", "-A"], target, echo)

    if not options.no_install:
        echo("Installing Python dependencies (uv sync)...")
        if not _run(["uv", "sync"], target, echo):
            echo("`uv sync` failed; skipping npm install and migrations.")
            return 1

        if not options.no_npm:
            echo("Installing frontend dependencies (npm install)...")
            _run(["npm", "install"], target, echo, allow_missing=True)

        if not options.no_migrate:
            fastogram_bin = target / ".venv" / "bin" / "fastogram"
            if fastogram_bin.is_file():
                echo("Running the initial migration...")
                _run([str(fastogram_bin), "migrate", "--force"], target, echo)
            else:
                echo("Skipping `fastogram migrate`: no `.venv/bin/fastogram` was installed.")

    echo(f"FastoGram application ready in [{target}]. `cd {name}` and run `fastogram dev` to get started.")
    return 0


def _run(argv: list[str], cwd: Path, echo, *, allow_missing: bool = False) -> bool:
    try:
        subprocess.run(argv, cwd=cwd, check=True)  # noqa: S603 - argv is built from fixed strings, never user input
    except FileNotFoundError:
        if allow_missing:
            echo(f"`{argv[0]}` was not found; skipping.")
            return True
        echo(f"`{argv[0]}` was not found.")
        return False
    except subprocess.CalledProcessError as exc:
        echo(f"`{' '.join(argv)}` failed with exit code {exc.returncode}.")
        return False
    return True
