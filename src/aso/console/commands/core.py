"""`serve`, `dev`, `tinker`, `env`, `about` (T-50, T-02, T-07).

`serve`/`dev` spawn child processes (uvicorn, `npm run dev`, optionally a queue worker) instead
of booting the app in this process. The command line each one builds is a plain function
(`build_serve_argv`, `build_dev_commands`) precisely so tests can assert on *what would run*
without ever starting a real server (BUILD.md: "never start long-running servers in tests").
"""

from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path
from typing import Any

from aso.console.command import Command
from aso.console.registry import register

_COLORS = ["cyan", "magenta", "yellow", "green", "blue"]


def build_serve_argv(host: str = "127.0.0.1", port: int = 8000) -> list[str]:
    return ["uvicorn", "bootstrap.app:create_app", "--factory", "--host", host, "--port", str(port)]


def build_dev_commands(*, port: int = 8000, vite_port: int = 5173, queue_enabled: bool = False) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {
        "server": ["uvicorn", "bootstrap.app:create_app", "--factory", "--reload", "--host", "127.0.0.1", "--port", str(port)],
        "vite": ["npm", "run", "dev", "--", "--port", str(vite_port)],
        "routes": [sys.argv[0] or "aso", "routes:generate", "--with-form", "--watch"],
    }
    if queue_enabled:
        commands["queue"] = [sys.argv[0] or "aso", "queue:work"]
    return commands


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    # "localhost" may be served on IPv4 or IPv6 (Node binds ::1 on some systems): check both.
    hosts = [("127.0.0.1", socket.AF_INET), ("::1", socket.AF_INET6)] if host == "localhost" else [(host, socket.AF_INET)]
    for address, family in hosts:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.25)
                if sock.connect_ex((address, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def find_free_port(port: int, host: str = "127.0.0.1", *, attempts: int = 10, taken: set[int] | None = None) -> int | None:
    """`port` if it is free, else the next free one within `attempts` tries (like `artisan serve`)."""
    for candidate in range(port, port + attempts):
        if candidate in (taken or set()):
            continue
        if not _port_in_use(candidate, host):
            return candidate
    return None


def app_url_for_port(url: str, port: int) -> str:
    """`APP_URL` with its port swapped for the one the server actually listens on, so links in
    emails and redirects keep working when `dev`/`serve` falls back to another port."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url or "http://localhost")
    host = parts.hostname or "localhost"
    return urlunsplit((parts.scheme or "http", f"{host}:{port}", parts.path, parts.query, parts.fragment))


def _pick_port(cmd: Command, label: str, port: int, host: str = "127.0.0.1", *, taken: set[int] | None = None) -> int | None:
    chosen = find_free_port(port, host, taken=taken)
    if chosen is None:
        cmd.error(f"The {label} port {port} and the next 9 ports are all in use. Pass a free one with --{'vite-' if label == 'Vite' else ''}port.")
    elif chosen != port:
        cmd.warn(f"The {label} port {port} is in use; using {chosen} instead.")
    return chosen


class ServeCommand(Command):
    signature = "serve {--host=127.0.0.1 : The host address to serve the application on} {--port=8000 : The port to serve the application on}"
    description = "Serve the application with the uvicorn development server"

    async def handle(self) -> int:
        host = str(self.option("host"))
        port = _pick_port(self, "application", int(self.option("port")), host)
        if port is None:
            return 1
        argv = build_serve_argv(host, port)
        self.info(f"Starting server: http://{host}:{port}")
        import subprocess

        return subprocess.call(argv, cwd=_base_path(), env=_child_env(port))


class DevCommand(Command):
    signature = "dev {--port=8000 : The application server port} {--vite-port=5173 : The Vite dev server port}"
    description = "Start the Python server, Vite, and the queue worker together"

    async def handle(self) -> int:
        port = _pick_port(self, "application", int(self.option("port")))
        if port is None:
            return 1
        vite_port = _pick_port(self, "Vite", int(self.option("vite-port")), "localhost", taken={port})
        if vite_port is None:
            return 1
        from aso.queue import drivers

        queue_enabled = drivers.connection_spec(drivers.driver_name()).get("driver") != "sync"
        commands = build_dev_commands(port=port, vite_port=vite_port, queue_enabled=queue_enabled)

        # Write the TypeScript route helpers *before* Vite starts: otherwise Vite's first
        # pre-transform races the watcher and logs "Failed to resolve import @/routes" (T-28).
        try:
            from aso.routing.registry import current_registry
            from aso.routing.ts_routes import generate

            generate(_base_path(), current_registry(), with_form=True)
        except Exception as exc:  # noqa: BLE001 - the watcher reports it again; still start the servers
            self.warn(f"Could not generate the TypeScript route helpers: {exc}")

        self.line("")
        self.info(f"  App   http://127.0.0.1:{port}   <- open this one")
        self.line(f"  Vite  http://localhost:{vite_port}   (assets + hot reload only)")
        self.line("")
        self.comment("Starting dev servers. (Ctrl+C to stop)")
        return await run_concurrently(commands, cwd=_base_path(), env=_child_env(port))


def _child_env(port: int) -> dict[str, str]:
    """The environment for child processes: unbuffered Python output (so `routes`/`queue` lines
    show up as they happen), `APP_URL` pointing at the port actually in use, and the running
    venv's `bin/` first on `PATH`, so `uvicorn` is found even without `uv run`/an activated venv."""
    import os

    from aso.config import config

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["PYTHONUNBUFFERED"] = "1"
    env["APP_URL"] = app_url_for_port(str(config("app.url") or "http://localhost"), port)
    return env


async def run_concurrently(commands: dict[str, list[str]], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    """`asyncio.create_subprocess_exec` per process, coloured prefixes, stop-all-on-exit (T-07)."""
    procs: dict[str, asyncio.subprocess.Process] = {}
    tasks: list[asyncio.Task[Any]] = []

    from rich.console import Console
    from rich.markup import escape

    stream_console = Console()

    async def _stream(name: str, proc: asyncio.subprocess.Process, color: str) -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            stream_console.print(f"[{color}]{name}[/{color}] | {escape(line)}", highlight=False, soft_wrap=True)

    # SIGTERM/SIGHUP (closing the terminal, `kill`) must stop the children too, exactly like
    # Ctrl+C does -- otherwise uvicorn and Vite keep the ports and `public/hot` stays behind.
    import signal

    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()
    handled: list[int] = []
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            loop.add_signal_handler(sig, main_task.cancel)  # type: ignore[union-attr]
            handled.append(sig)
        except (NotImplementedError, RuntimeError, ValueError):  # Windows, or not the main thread
            pass

    try:
        for i, (name, argv) in enumerate(commands.items()):
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=cwd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            procs[name] = proc
            tasks.append(asyncio.ensure_future(_stream(name, proc, _COLORS[i % len(_COLORS)])))
        waiters = [asyncio.ensure_future(p.wait()) for p in procs.values()]
        done, _pending = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        return next(iter(done)).result()
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    finally:
        for proc in procs.values():
            if proc.returncode is None:
                proc.terminate()
        await asyncio.gather(*(p.wait() for p in procs.values()), return_exceptions=True)
        for task in tasks:
            task.cancel()
        for sig in handled:
            loop.remove_signal_handler(sig)


class TinkerCommand(Command):
    signature = "tinker"
    description = "Interact with your application"

    async def handle(self) -> int:
        import sys as _sys

        from aso.console.migrations import import_app_models

        import_app_models(_base_path())
        namespace = _tinker_namespace()
        if not _sys.stdin.isatty():
            self.warn("Tinker needs an interactive terminal.")
            return 0

        from aso.database.scope import open_scope

        async with open_scope():
            try:
                import IPython
            except ImportError:
                await _plain_async_repl(namespace, self)
                return 0
            await asyncio.to_thread(IPython.start_ipython, argv=[], user_ns=namespace)
        return 0


def _tinker_namespace() -> dict[str, Any]:
    from aso.database import DB, Model

    namespace: dict[str, Any] = {"DB": DB, "Model": Model}
    import sys as _sys

    for mod_name, module in list(_sys.modules.items()):
        if mod_name.startswith("app.models."):
            for attr, value in vars(module).items():
                if isinstance(value, type) and issubclass(value, Model) and not attr.startswith("_"):
                    namespace[attr] = value
    return namespace


async def _plain_async_repl(namespace: dict[str, Any], cmd: Command) -> None:
    """IPython is not installed: a minimal `await`-capable REPL (`python -m asyncio` behaviour,
    T-50 open question #2)."""
    import code

    cmd.comment("IPython is not installed; falling back to a plain REPL (top-level `await` works).")
    console = code.InteractiveConsole(namespace)
    while True:
        try:
            line = await asyncio.to_thread(input, ">>> ")
        except EOFError:
            break
        if line.strip() in ("exit", "exit()", "quit", "quit()"):
            break
        source = line
        if "await " in source and not source.strip().startswith(("async ", "def ", "class ")):
            source = f"__aso_result = {source}"
            wrapped = f"async def __aso_coro():\n    global __aso_result\n    {source}\n"
            try:
                exec(compile(wrapped, "<tinker>", "exec"), namespace)  # noqa: S102
                await namespace["__aso_coro"]()
                if namespace.get("__aso_result") is not None:
                    print(repr(namespace["__aso_result"]))  # noqa: T201
            except Exception as exc:  # noqa: BLE001 - print and keep the REPL alive
                print(f"{type(exc).__name__}: {exc}")  # noqa: T201
        else:
            console.push(source)


class EnvCommand(Command):
    signature = "env"
    description = "Display the current framework environment"

    async def handle(self) -> int:
        from aso.foundation.application import environment

        self.line(environment())
        return 0


class AboutCommand(Command):
    signature = "about"
    description = "Display basic information about your application"

    async def handle(self) -> int:
        from aso.config import config
        from aso.foundation.application import environment

        rows = [
            ["Application Name", config("app.name") or ""],
            ["Environment", environment()],
            ["Debug Mode", str(bool(config("app.debug")))],
            ["URL", config("app.url") or ""],
            ["Database Driver", config("database.default") or ""],
            ["Session Driver", config("session.driver") or ""],
            ["Queue Connection", config("queue.default") or "sync"],
            ["Cache Store", config("cache.default") or ""],
        ]
        self.table(["Property", "Value"], rows)
        return 0


def _base_path() -> Path:
    from aso.foundation.paths import base_path

    return base_path()


def register_all() -> None:
    for cls in (ServeCommand, DevCommand, TinkerCommand, EnvCommand, AboutCommand):
        register(cls, source="framework")
