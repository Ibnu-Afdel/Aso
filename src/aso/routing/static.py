"""Serving `public/` (T-07, T-43): files are served at the site root, after the routes.

The web group's catch-all fallback route is the last route, so an unmatched URL reaches it. Before
running the web stack (session, CSRF, the React 404 page), it checks for a real file in `public/`
and serves it with Starlette's `StaticFiles`, the way a web server serves Laravel's `public/`
before PHP runs. `follow_symlink=True` so `public/storage` (from `storage:link`) works.
"""

from __future__ import annotations

from pathlib import Path

from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from aso.foundation.paths import public_path


class PublicFilesFirst:
    def __init__(self, app: ASGIApp, directory: Path | None = None) -> None:
        self.app = app
        self.directory = directory or public_path()
        self._static: StaticFiles | None = None

    def _file_for(self, path: str) -> bool:
        relative = path.lstrip("/")
        if not relative or not self.directory.is_dir():
            return False
        parts = Path(relative).parts
        if any(part in ("..", "") or part.startswith(".") for part in parts):
            return False  # no traversal, no dotfiles (.env would never be here, but be strict)
        if parts[0] == "hot":
            return False
        return (self.directory / relative).is_file()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in ("GET", "HEAD") and self._file_for(scope["path"]):
            if self._static is None:
                self._static = StaticFiles(directory=self.directory, follow_symlink=True)
            await self._static(scope, receive, send)
            return
        await self.app(scope, receive, send)
