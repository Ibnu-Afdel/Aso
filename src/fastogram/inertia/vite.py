"""Vite integration (T-07, D-023): dev-server tags from `public/hot`, manifest tags in production.

Mirrors Laravel's `Illuminate\\Foundation\\Vite`. `public/hot` holds the dev-server URL while
`vite dev` runs; otherwise `public/build/manifest.json` (written by `vite build`) is read and
cached, re-read when its modification time changes.
"""

from __future__ import annotations

import json
from typing import Any

from markupsafe import Markup

from fastogram.foundation.paths import public_path

STYLE_EXTENSIONS = (".css", ".scss", ".sass", ".less", ".styl", ".stylus", ".pcss", ".postcss")
PAGE_PREFIX = "resources/js/pages/"

_manifest_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class ViteManifestNotFound(RuntimeError):
    def __init__(self, entry: str) -> None:
        super().__init__(f'Unable to locate file in the Vite manifest: "{entry}". Run `npm run build`.')
        self.entry = entry


def _hot_url() -> str | None:
    hot = public_path("hot")
    if not hot.exists():
        return None
    return hot.read_text().strip().rstrip("/")


def _manifest() -> dict[str, Any] | None:
    manifest_file = public_path("build", "manifest.json")
    if not manifest_file.exists():
        return None
    mtime = manifest_file.stat().st_mtime
    key = str(manifest_file)
    cached = _manifest_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    data = json.loads(manifest_file.read_text())
    _manifest_cache[key] = (mtime, data)
    return data


def manifest_hash() -> str:
    """The MD5 hex digest of the manifest file, or `""` in dev / without a build (T-17)."""
    import hashlib

    if _hot_url() is not None:
        return ""
    manifest_file = public_path("build", "manifest.json")
    if not manifest_file.exists():
        return ""
    return hashlib.md5(manifest_file.read_bytes()).hexdigest()


def vite_react_refresh() -> Markup:
    """The React Refresh preamble in dev; empty in production."""
    url = _hot_url()
    if url is None:
        return Markup("")
    return Markup(
        '<script type="module">\n'
        f'import RefreshRuntime from "{url}/@react-refresh";\n'
        "RefreshRuntime.injectIntoGlobalHook(window);\n"
        "window.$RefreshReg$ = () => {};\n"
        "window.$RefreshSig$ = () => (type) => type;\n"
        "window.__vite_plugin_react_preamble_installed__ = true;\n"
        "</script>"
    )


def vite(*entries: str) -> Markup:
    """`<script>`/`<link>` tags for each entry: the dev-server client in dev, hashed manifest
    tags (plus CSS and `modulepreload` of imported chunks) in production.

    A missing entry under `resources/js/pages/` (an Inertia page the client code-splits into,
    never a Vite build input) is skipped silently, like Laravel's optional `@vite` entries.
    """
    url = _hot_url()
    if url is not None:
        tags = [f'<script type="module" src="{url}/@vite/client"></script>']
        for entry in entries:
            if entry.endswith(STYLE_EXTENSIONS):
                tags.append(f'<link rel="stylesheet" href="{url}/{entry}">')
            else:
                tags.append(f'<script type="module" src="{url}/{entry}"></script>')
        return Markup("\n".join(tags))

    manifest = _manifest()
    if manifest is None:
        return Markup("")

    tags: list[str] = []
    preloaded: set[str] = set()

    def emit_preloads(entry_name: str) -> None:
        chunk = manifest.get(entry_name)
        if chunk is None:
            return
        for imported in chunk.get("imports", []):
            if imported in preloaded:
                continue
            preloaded.add(imported)
            imported_chunk = manifest.get(imported, {})
            file = imported_chunk.get("file")
            if file:
                tags.append(f'<link rel="modulepreload" href="/build/{file}">')
            for css in imported_chunk.get("css", []):
                tags.append(f'<link rel="stylesheet" href="/build/{css}">')
            emit_preloads(imported)

    for entry in entries:
        chunk = manifest.get(entry)
        if chunk is None:
            if entry.startswith(PAGE_PREFIX):
                continue
            raise ViteManifestNotFound(entry)
        for css in chunk.get("css", []):
            tags.append(f'<link rel="stylesheet" href="/build/{css}">')
        tags.append(f'<script type="module" src="/build/{chunk["file"]}"></script>')
        emit_preloads(entry)
    return Markup("\n".join(tags))


def vite_asset(path: str) -> str:
    """The hashed URL of one processed asset, for a Jinja template (not a TSX import)."""
    url = _hot_url()
    if url is not None:
        return f"{url}/{path}"
    manifest = _manifest()
    if manifest is None or path not in manifest:
        raise ViteManifestNotFound(path)
    return f"/build/{manifest[path]['file']}"


def inertia_head(fallback: str = "") -> Markup:
    """Head tags from server-side rendering when SSR is on; otherwise `fallback` (usually the
    page `<title>`). SSR is not implemented yet, so this always prints `fallback`."""
    return Markup(fallback)
