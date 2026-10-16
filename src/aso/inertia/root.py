"""Root template rendering (`resources/views/<view>.html`, Jinja2) (T-07, T-16).

The Jinja environment has autoescape on and exposes the Vite helpers, `inertia_head()` and
`config()` as globals. `inertia_app()` is bound per render call because it needs this response's
page object; everything else is a plain zero-argument (or argument-taking) global.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aso.foundation.paths import resource_path
from aso.inertia.vite import inertia_head, vite, vite_asset, vite_react_refresh


@lru_cache(maxsize=4)
def _environment(views_dir: str) -> Environment:
    env = Environment(loader=FileSystemLoader(views_dir), autoescape=select_autoescape(["html", "xml"]))
    env.globals["vite"] = vite
    env.globals["vite_react_refresh"] = vite_react_refresh
    env.globals["vite_asset"] = vite_asset
    env.globals["inertia_head"] = inertia_head
    try:
        from aso.config import config

        env.globals["config"] = config
    except ImportError:
        pass
    return env


def render_root_view(view: str, page: dict[str, Any], view_data: dict[str, Any] | None = None) -> str:
    from aso.inertia.response import inertia_app

    env = _environment(str(resource_path("views")))
    template = env.get_template(view)
    return template.render(page=page, inertia_app=lambda: inertia_app(page), **(view_data or {}))
