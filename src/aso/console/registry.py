"""Command registration, discovery, and `call()`/`call_output()` (T-50).

One shared registry for both framework commands (registered by the modules in
`aso.console.commands`) and user commands (`app/console/commands/*.py`, plus closures
declared with `@command(...)` in `routes/console.py`). `call()` runs either kind through the
exact same runner `handle()` the CLI uses, inside a fresh `DB.scope()` (T-30): models work,
`session()`/`auth()` do not (there is no request).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from rich.console import Console

from aso.console.command import Command
from aso.console.io import CommandIO
from aso.console.signature import ParsedSignature, parse_signature

__all__ = ["CommandNotFound", "call", "call_output", "command"]


class CommandNotFound(RuntimeError):
    pass


@dataclass
class RegisteredCommand:
    name: str
    description: str
    parsed: ParsedSignature
    factory: Callable[[CommandIO, dict[str, Any], dict[str, Any]], Command]
    source: str = "framework"  # "framework" | "user"


_registry: dict[str, RegisteredCommand] = {}
_last_output: str = ""


def reset_registry(*, keep: str = "framework") -> None:
    """Drop registered commands. `keep="framework"` only clears user/closure commands (the
    default, used before re-running `routes/console.py` and re-scanning `app/console/commands/`);
    `keep="none"` clears everything (test isolation)."""
    if keep == "none":
        _registry.clear()
        return
    for name in [n for n, r in _registry.items() if r.source != "framework"]:
        del _registry[name]


def all_commands() -> list[RegisteredCommand]:
    return sorted(_registry.values(), key=lambda r: r.name)


def get(name: str) -> RegisteredCommand | None:
    return _registry.get(name)


def register(command_cls: type[Command], *, source: str = "user") -> RegisteredCommand:
    """Register a `Command` subclass by its own `signature`/`description` class attributes.

    `source="user"` by default, so an ad-hoc `register(cls)` call (tests, a REPL) is cleared by
    `reset_registry()`'s default `keep="framework"`. The `aso.console.commands.*` modules
    pass `source="framework"` explicitly."""
    parsed = parse_signature(command_cls.signature)
    if not parsed.name:
        raise ValueError(f"{command_cls.__name__}.signature must start with a command name, e.g. 'report:send'.")

    def factory(io: CommandIO, arguments: dict[str, Any], options: dict[str, Any]) -> Command:
        return command_cls(io, arguments, options)

    registered = RegisteredCommand(parsed.name, command_cls.description, parsed, factory, source)
    _registry[parsed.name] = registered
    return registered


def register_closure(signature: str, description: str, fn: Callable[[Command], Any], *, source: str = "user") -> RegisteredCommand:
    """Register a closure command (`@command(...)` in `routes/console.py`): `fn(self)` runs as
    the command's `handle()`, with `self` bound to the `Command` instance so `fn` can call
    `self.argument()` / `self.info()` / etc."""
    parsed = parse_signature(signature)

    class _ClosureCommand(Command):
        pass

    _ClosureCommand.signature = signature
    _ClosureCommand.description = description

    async def handle(self: Command) -> int:
        result = fn(self)
        if hasattr(result, "__await__"):
            result = await result
        return 0 if result is None else int(result)

    _ClosureCommand.handle = handle  # type: ignore[method-assign]

    def factory(io: CommandIO, arguments: dict[str, Any], options: dict[str, Any]) -> Command:
        return _ClosureCommand(io, arguments, options)

    registered = RegisteredCommand(parsed.name, description, parsed, factory, source)
    _registry[parsed.name] = registered
    return registered


def command(signature: str, description: str = "") -> Callable[[Callable[[Command], Any]], Callable[[Command], Any]]:
    """`@command("report:send {user_id}")` in `routes/console.py` (T-50)."""

    def decorator(fn: Callable[[Command], Any]) -> Callable[[Command], Any]:
        register_closure(signature, description, fn)
        return fn

    return decorator


# ---------------------------------------------------------------- binding params -> arguments/options


def bind_params(parsed: ParsedSignature, params: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """`{"user_id": 1, "--queue": True}` (Laravel's `Artisan::call()` form) -> `(arguments, options)`.

    Both plain option names and `--`-prefixed ones are accepted, so `call()` callers and the CLI
    bridge can use the same dict shape.
    """
    remaining = dict(params or {})
    arguments: dict[str, Any] = {}
    for arg in parsed.arguments:
        if arg.name in remaining:
            arguments[arg.name] = remaining.pop(arg.name)
        elif arg.default is not None:
            arguments[arg.name] = arg.default
        elif arg.optional or arg.is_list:
            arguments[arg.name] = [] if arg.is_list else None
        else:
            raise ValueError(f"Missing required argument {arg.name!r}.")
    options: dict[str, Any] = {}
    for opt in parsed.options:
        key = f"--{opt.name}"
        if key in remaining:
            options[opt.name] = remaining.pop(key)
        elif opt.name in remaining:
            options[opt.name] = remaining.pop(opt.name)
        else:
            options[opt.name] = opt.default
    return arguments, options


# ---------------------------------------------------------------- running


async def run_registered(
    registered: RegisteredCommand, params: dict[str, Any] | None, *, io: CommandIO | None = None, no_interaction: bool = False
) -> int:
    """The one runner both `call()` and the CLI use: parse params, instantiate, `handle()`,
    inside a fresh `DB.scope()` (T-30)."""
    from aso.database.scope import open_scope

    arguments, options = bind_params(registered.parsed, params)
    io = io or CommandIO(no_interaction=no_interaction)
    instance = registered.factory(io, arguments, options)
    async with open_scope():
        return await instance.handle()


async def call(name: str, params: dict[str, Any] | None = None, *, io: CommandIO | None = None) -> int:
    """`await call("report:send", {"user_id": 1, "--queue": True})` (T-50). Returns the exit
    code; output is captured, not printed -- read it with `call_output()` right after."""
    global _last_output
    registered = _registry.get(name)
    if registered is None:
        raise CommandNotFound(f'Command "{name}" is not defined.')
    buffer = StringIO()
    capturing_io = io or CommandIO(Console(file=buffer, force_terminal=False, no_color=True, width=120, markup=False))
    exit_code = await run_registered(registered, params, io=capturing_io)
    if io is None:
        _last_output = buffer.getvalue()
    return exit_code


def call_output() -> str:
    """The captured output of the most recent `call()` (T-50)."""
    return _last_output


def _reset_call_output() -> None:
    global _last_output
    _last_output = ""


# ---------------------------------------------------------------- discovery


def discover_user_commands(base_path: Path) -> list[type[Command]]:
    """Import every module in `app/console/commands/` and register its `Command` subclasses."""
    directory = base_path / "app" / "console" / "commands"
    found: list[type[Command]] = []
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"app.console.commands.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        import sys

        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, Command) and value is not Command:
                register(value, source="user")
                found.append(value)
    return found


def load_console_routes(base_path: Path) -> None:
    """Run `routes/console.py` (fresh each time): `@command(...)` closures and `schedule.*`."""
    from aso.console.schedule import schedule as _schedule

    path = base_path / "routes" / "console.py"
    _schedule.clear()
    if not path.exists():
        return
    import runpy

    runpy.run_path(str(path), run_name="routes.console")
