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

from fastogram.console.command import Command
from fastogram.console.registry import register

_COLORS = ["cyan", "magenta", "yellow", "green", "blue"]


def build_serve_argv(host: str = "127.0.0.1", port: int = 8000) -> list[str]:
    return ["uvicorn", "bootstrap.app:create_app", "--factory", "--host", host, "--port", str(port)]


def build_dev_commands(*, port: int = 8000, vite_port: int = 5173, queue_enabled: bool = False) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {
        "server": ["uvicorn", "bootstrap.app:create_app", "--factory", "--reload", "--host", "127.0.0.1", "--port", str(port)],
        "vite": ["npm", "run", "dev", "--", "--port", str(vite_port)],
    }
    if queue_enabled:
        commands["queue"] = [sys.argv[0] or "fastogram", "queue:work"]
    return commands


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


class ServeCommand(Command):
    signature = "serve {--host=127.0.0.1 : The host address to serve the application on} {--port=8000 : The port to serve the application on}"
    description = "Serve the application with the uvicorn development server"

    async def handle(self) -> int:
        host = str(self.option("host"))
        port = int(self.option("port"))
        if _port_in_use(port, host):
            self.error(f"Port {port} is already in use.")
            return 1
        argv = build_serve_argv(host, port)
        self.info(f"Starting server: http://{host}:{port}")
        import subprocess

        return subprocess.call(argv, cwd=_base_path())


class DevCommand(Command):
    signature = "dev {--port=8000 : The application server port} {--vite-port=5173 : The Vite dev server port}"
    description = "Start the Python server, Vite, and the queue worker together"

    async def handle(self) -> int:
        port = int(self.option("port"))
        vite_port = int(self.option("vite-port"))
        for label, p in (("application", port), ("Vite", vite_port)):
            if _port_in_use(p):
                self.error(f"The {label} port {p} is already in use.")
                return 1
        from fastogram.queue import drivers

        queue_enabled = drivers.connection_spec(drivers.driver_name()).get("driver") != "sync"
        commands = build_dev_commands(port=port, vite_port=vite_port, queue_enabled=queue_enabled)
        self.info("Starting dev servers. (Ctrl+C to stop)")
        return await run_concurrently(commands, cwd=_base_path())


async def run_concurrently(commands: dict[str, list[str]], *, cwd: Path) -> int:
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
            stream_console.print(f"[{color}]{name}[/{color}] | {escape(line)}", highlight=False)

    try:
        for i, (name, argv) in enumerate(commands.items()):
            proc = await asyncio.create_subprocess_exec(
                *argv, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
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


class TinkerCommand(Command):
    signature = "tinker"
    description = "Interact with your application"

    async def handle(self) -> int:
        import sys as _sys

        from fastogram.console.migrations import import_app_models

        import_app_models(_base_path())
        namespace = _tinker_namespace()
        if not _sys.stdin.isatty():
            self.warn("Tinker needs an interactive terminal.")
            return 0

        from fastogram.database.scope import open_scope

        async with open_scope():
            try:
                import IPython
            except ImportError:
                await _plain_async_repl(namespace, self)
                return 0
            await asyncio.to_thread(IPython.start_ipython, argv=[], user_ns=namespace)
        return 0


def _tinker_namespace() -> dict[str, Any]:
    from fastogram.database import DB, Model

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
            source = f"__fastogram_result = {source}"
            wrapped = f"async def __fastogram_coro():\n    global __fastogram_result\n    {source}\n"
            try:
                exec(compile(wrapped, "<tinker>", "exec"), namespace)  # noqa: S102
                await namespace["__fastogram_coro"]()
                if namespace.get("__fastogram_result") is not None:
                    print(repr(namespace["__fastogram_result"]))  # noqa: T201
            except Exception as exc:  # noqa: BLE001 - print and keep the REPL alive
                print(f"{type(exc).__name__}: {exc}")  # noqa: T201
        else:
            console.push(source)


class EnvCommand(Command):
    signature = "env"
    description = "Display the current framework environment"

    async def handle(self) -> int:
        from fastogram.foundation.application import environment

        self.line(environment())
        return 0


class AboutCommand(Command):
    signature = "about"
    description = "Display basic information about your application"

    async def handle(self) -> int:
        from fastogram.config import config
        from fastogram.foundation.application import environment

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
    from fastogram.foundation.paths import base_path

    return base_path()


def register_all() -> None:
    for cls in (ServeCommand, DevCommand, TinkerCommand, EnvCommand, AboutCommand):
        register(cls, source="framework")
