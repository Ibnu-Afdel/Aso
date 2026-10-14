"""Project paths: `base_path()`, `app_path()`, ... (Laravel's path helpers)."""

from __future__ import annotations

import os
from pathlib import Path

_base: Path | None = None


def set_base_path(path: str | Path) -> Path:
    global _base
    p = Path(path).resolve()
    if p.is_file():
        p = p.parent
    # `Application.configure(base_path=__file__)` is called from bootstrap/app.py
    if p.name == "bootstrap":
        p = p.parent
    _base = p
    return p


def base_path(*parts: str) -> Path:
    root = _base or Path(os.environ.get("FASTOGRAM_BASE_PATH", os.getcwd())).resolve()
    return root.joinpath(*parts)


def app_path(*parts: str) -> Path:
    return base_path("app", *parts)


def config_path(*parts: str) -> Path:
    return base_path("config", *parts)


def database_path(*parts: str) -> Path:
    return base_path("database", *parts)


def public_path(*parts: str) -> Path:
    return base_path("public", *parts)


def resource_path(*parts: str) -> Path:
    return base_path("resources", *parts)


def storage_path(*parts: str) -> Path:
    return base_path("storage", *parts)
