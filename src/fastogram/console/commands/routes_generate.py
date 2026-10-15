"""`routes:generate` (T-28): write `resources/js/routes/**`, `resources/js/actions/**` and
`resources/js/wayfinder/index.ts` from the compiled route registry.

By the time `handle()` runs, the CLI has already booted the app (`boot_console()` calls
`create_app()`, which loads and compiles every route -- same as `route:list`, T-50), so a plain
`routes:generate` just reads `current_registry()` and hands it to the pure generator in
`fastogram.routing.ts_routes`. `--watch` re-boots the app (so the route registry is fresh) and
regenerates whenever a file under `routes/` or `app/http/controllers/` changes (T-28
"Watching"); this is the piece `fastogram dev` is meant to run alongside uvicorn and Vite --
see the note in the build report about the one line `build_dev_commands()` (in
`fastogram.console.commands.core`, outside this task's files) still needs to start it.
"""

from __future__ import annotations

from pathlib import Path

from fastogram.console.command import Command
from fastogram.console.registry import register


class RoutesGenerateCommand(Command):
    signature = (
        "routes:generate "
        "{--skip-actions : Do not write resources/js/actions} "
        "{--skip-routes : Do not write resources/js/routes} "
        "{--with-form : Add a .form() helper to every generated route/action} "
        "{--watch : Keep running, regenerating on changes under routes/ and app/http/controllers/}"
    )
    description = "Generate typed TypeScript route and action helpers (T-28)"

    async def handle(self) -> int:
        from fastogram.foundation.paths import base_path

        root = base_path()
        skip_routes = bool(self.option("skip-routes"))
        skip_actions = bool(self.option("skip-actions"))
        with_form = bool(self.option("with-form"))

        self._generate_once(root, skip_routes, skip_actions, with_form)

        if self.option("watch"):
            await self._watch(root, skip_routes, skip_actions, with_form)
        return 0

    def _generate_once(self, root: Path, skip_routes: bool, skip_actions: bool, with_form: bool) -> None:
        from fastogram.routing.registry import current_registry
        from fastogram.routing.ts_routes import generate

        written = generate(
            root,
            current_registry(),
            skip_routes=skip_routes,
            skip_actions=skip_actions,
            with_form=with_form,
        )
        changed = sum(1 for was_changed in written.values() if was_changed)
        self.info(f"Wrote {len(written)} file(s), {changed} changed.")

    async def _watch(self, root: Path, skip_routes: bool, skip_actions: bool, with_form: bool) -> None:
        from watchfiles import awatch

        from fastogram.console.boot import boot_console

        watched = [p for p in (root / "routes", root / "app" / "http" / "controllers") if p.exists()]
        if not watched:
            self.warn("Nothing to watch: neither routes/ nor app/http/controllers/ exists.")
            return
        self.info("Watching for route changes (Ctrl+C to stop)...")
        async for _changes in awatch(*watched):
            try:
                boot_console(root)  # re-imports bootstrap.app and recompiles the route registry
            except Exception as exc:  # noqa: BLE001 - a bad route file must not kill the watcher
                self.error(f"routes:generate: {exc}")
                continue
            self._generate_once(root, skip_routes, skip_actions, with_form)


def register_all() -> None:
    register(RoutesGenerateCommand, source="framework")
