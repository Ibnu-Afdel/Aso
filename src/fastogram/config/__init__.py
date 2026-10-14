"""Configuration: `env()` and `config()` (T-03, D-012)."""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import types
from pathlib import Path
from typing import Any

__all__ = ["config", "env", "load", "load_environment", "set_config", "all_config"]

_MISSING = object()
_CASTS = {
    "true": True,
    "(true)": True,
    "false": False,
    "(false)": False,
    "null": None,
    "(null)": None,
    "empty": "",
    "(empty)": "",
}

_config: dict[str, Any] = {}


def env(key: str, default: Any = None) -> Any:
    """Read an environment variable with Laravel's casting rules.

    `"true"/"false"` become booleans, `"null"` becomes `None`, `"empty"` becomes `""`.
    Matching is case-insensitive. Surrounding quotes are not stripped here: python-dotenv already
    removed them when it loaded `.env`.
    """
    value = os.environ.get(key, _MISSING)
    if value is _MISSING:
        return default() if callable(default) else default
    assert isinstance(value, str)
    lowered = value.lower()
    if lowered in _CASTS:
        return _CASTS[lowered]
    return value


def config(key: str | None = None, default: Any = None) -> Any:
    """Read a config value with dot syntax: `config("database.connections.sqlite.database")`.

    The first segment is the file in `config/`; later segments walk module variables and nested
    dicts. Returns `default` when any segment is missing. `config()` with no key returns everything.
    """
    if key is None:
        return _config
    node: Any = _config
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, (list, tuple)) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return default
    return node


def set_config(key: str, value: Any) -> None:
    """Set a config value at runtime (tests, `config(["a.b" => ...])` in Laravel)."""
    parts = key.split(".")
    node = _config
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def all_config() -> dict[str, Any]:
    return _config


def load_environment(base_path: Path) -> None:
    """Load `.env` (or `.env.testing` when `APP_ENV=testing`) into `os.environ`.

    Real environment variables win (`override=False`), as in Laravel.
    """
    from dotenv import load_dotenv

    testing = os.environ.get("APP_ENV") == "testing"
    candidate = base_path / ".env.testing" if testing else None
    if candidate is not None and candidate.exists():
        load_dotenv(candidate, override=False)
    else:
        load_dotenv(base_path / ".env", override=False)


def _module_values(module: types.ModuleType) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        if isinstance(value, types.ModuleType) or inspect.isfunction(value) or inspect.isclass(value):
            continue
        if inspect.isbuiltin(value):
            continue
        values[name] = value
    return values


def load(config_dir: Path) -> dict[str, Any]:
    """Import every module in `config/` and index its public variables.

    Modules are imported by file path under the name `config.<file>`, so a fresh import happens
    each time (`create_app()` may run more than once in one process, e.g. in tests).
    """
    _config.clear()
    if not config_dir.is_dir():
        return _config
    for path in sorted(config_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        name = f"config.{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _config[path.stem] = _module_values(module)
    return _config
