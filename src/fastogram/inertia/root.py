"""Root template rendering (`resources/views/app.html`, Jinja2) and Vite tags (T-07, D-023).

SEED (spine): manifest tags + dev-server tags from `public/hot`. The inertia package task
completes `vite_react_refresh`, `vite_asset`, `inertia_head`, CSS of imported chunks, preload tags.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from fastogram.foundation.paths import public_path, resource_path


@lru_cache(maxsize=4)
def _environment(views_dir: str) -> Environment:
    env = Environment(loader=FileSystemLoader(views_dir), autoescape=select_autoescape(["html", "xml"]))
    env.globals["vite"] = vite
    return env


def vite(*entries: str) -> Markup:
    hot = public_path("hot")
    if hot.exists():
        url = hot.read_text().strip().rstrip("/")
        tags = [f'<script type="module" src="{url}/@vite/client"></script>']
        tags += [f'<script type="module" src="{url}/{e}"></script>' for e in entries]
        return Markup("\n".join(tags))
    manifest_file = public_path("build", "manifest.json")
    if not manifest_file.exists():
        return Markup("")
    manifest = json.loads(manifest_file.read_text())
    tags = []
    for entry in entries:
        chunk = manifest.get(entry)
        if chunk is None:
            raise RuntimeError(f"Unable to locate file in Vite manifest: {entry}. Run `npm run build`.")
        for css in chunk.get("css", []):
            tags.append(f'<link rel="stylesheet" href="/build/{css}">')
        tags.append(f'<script type="module" src="/build/{chunk["file"]}"></script>')
    return Markup("\n".join(tags))


def render_root_view(view: str, page: dict[str, Any], view_data: dict[str, Any] | None = None) -> str:
    from fastogram.inertia.response import inertia_app

    env = _environment(str(resource_path("views")))
    template = env.get_template(view)
    return template.render(page=page, inertia_app=lambda: inertia_app(page), **(view_data or {}))
