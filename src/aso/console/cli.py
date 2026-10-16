"""The `aso` CLI (T-50, D-014, S-4): a Typer app whose commands keep artisan's colon
names, grouped by prefix in `--help` (`rich_help_panel`).

Framework commands and user commands (`app/console/commands/`, `routes/console.py`) share one
mechanism: both are `Command` subclasses registered in `aso.console.registry`, and both
get a dynamically built `click.Command` from their parsed `signature` (`_build_click_command`),
added directly to the Typer app's underlying `click.Group`. `--help`/`list` and `call()` see the
exact same set of commands either way (T-50 "How it works").
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import click
import typer

from aso.console import boot
from aso.console.registry import RegisteredCommand, all_commands, run_registered
from aso.console.signature import ParsedSignature

__all__ = ["build_cli", "main"]


def _panel_for(name: str) -> str:
    return name.split(":", 1)[0] if ":" in name else "Available commands"


def _click_params(parsed: ParsedSignature) -> list[click.Parameter]:
    params: list[click.Parameter] = []
    for arg in parsed.arguments:
        if arg.is_list:
            params.append(click.Argument([arg.name], nargs=-1, required=not arg.optional))
        elif arg.optional or arg.default is not None:
            params.append(click.Argument([arg.name], required=False, default=arg.default))
        else:
            params.append(click.Argument([arg.name]))
    for opt in parsed.options:
        decls = [f"-{opt.shortcut}", f"--{opt.name}"] if opt.shortcut else [f"--{opt.name}"]
        help_text = opt.description or None
        if opt.kind == "flag":
            params.append(click.Option(decls, is_flag=True, default=False, help=help_text))
        elif opt.kind == "list":
            params.append(click.Option(decls, multiple=True, default=(), help=help_text))
        else:
            params.append(click.Option(decls, default=opt.default, help=help_text))
    return params


def _help_option() -> click.Option:
    """A plain `click.Command`'s default `--help` raises `click.exceptions.Exit`, which Typer's
    own `main()` wrapper does not recognise (it only catches its own `typer.exceptions.Exit`) --
    dynamically-added commands get misreported as exit code 1 even though the help text itself
    prints correctly. Raising a bare `SystemExit(0)` here sidesteps that interop gap."""

    def _show_help(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
        if value and not ctx.resilient_parsing:
            click.echo(ctx.get_help())
            raise SystemExit(0)

    return click.Option(
        ["--help"], is_flag=True, expose_value=False, is_eager=True, callback=_show_help, help="Show this message and exit."
    )


def build_click_command(registered: RegisteredCommand) -> click.Command:
    """A dynamic `click.Command` from `registered.parsed` -- the same thing a user command's
    `signature` gets, so framework and user commands expose an identical CLI surface."""
    parsed = registered.parsed

    def callback(**kwargs: Any) -> None:
        params: dict[str, Any] = {}
        for arg in parsed.arguments:
            value = kwargs.get(arg.name)
            params[arg.name] = list(value) if arg.is_list and value is not None else value
        for opt in parsed.options:
            dest = opt.name.replace("-", "_")
            value = kwargs.get(dest)
            params[f"--{opt.name}"] = list(value) if opt.kind == "list" else value
        exit_code = asyncio.run(run_registered(registered, params))
        raise SystemExit(exit_code)

    command = click.Command(
        name=registered.name,
        params=[*_click_params(parsed), _help_option()],
        callback=callback,
        help=registered.description or None,
        add_help_option=False,
    )
    command.rich_help_panel = _panel_for(registered.name)  # type: ignore[attr-defined]
    return command


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        try:
            v = version("aso")
        except Exception:  # noqa: BLE001 - editable/dev installs may not report a version
            v = "dev"
        typer.echo(f"Aso {v}")
        raise typer.Exit()


def build_cli(project_root: Path | None) -> click.BaseCommand:
    """The fully assembled CLI. `project_root=None` -> only `new`/`list`/`--version` (D-014)."""
    app = typer.Typer(
        help="Aso — a Laravel-style framework for Python",
        no_args_is_help=True,
        rich_markup_mode="rich",
        add_completion=False,
    )

    @app.callback(invoke_without_command=True)
    def _root(
        version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True, help="Show the Aso version."),
    ) -> None:
        pass

    @app.command("new", rich_help_panel="Available commands")
    def _new(
        name: str = typer.Argument(..., help="The application directory to create."),
        kit: str = typer.Option("react", "--kit", help="Frontend starter kit (only 'react' in v1)."),
        database: str = typer.Option("sqlite", "--database", help="Database dialect: sqlite, pgsql or mysql."),
        no_install: bool = typer.Option(False, "--no-install", help="Skip `uv sync`."),
        no_npm: bool = typer.Option(False, "--no-npm", help="Skip `npm install`."),
        no_migrate: bool = typer.Option(False, "--no-migrate", help="Skip the initial `aso migrate`."),
        git: bool = typer.Option(False, "--git", help="Initialise a git repository."),
        dev: bool = typer.Option(
            False, "--dev", help="Keep `aso` as an editable path dependency on this dev checkout, instead of pinning a released version."
        ),
        force: bool = typer.Option(False, "--force", help="Overwrite the target directory if it already exists."),
    ) -> None:
        """Create a new Aso application."""
        from aso.console.commands.new import NewAppOptions
        from aso.console.commands.new import new as new_command

        options = NewAppOptions(
            kit=kit,
            database=database,
            no_install=no_install,
            no_npm=no_npm,
            no_migrate=no_migrate,
            git=git,
            dev=dev,
            force=force,
        )
        exit_code = asyncio.run(new_command(name, options))
        raise SystemExit(exit_code)

    @app.command("list", rich_help_panel="Available commands")
    def _list() -> None:
        """List all registered commands."""
        for registered in all_commands():
            typer.echo(f"{registered.name}\t{registered.description}")

    group = typer.main.get_command(app)

    if project_root is not None:
        boot.boot_console(project_root)
        for registered in all_commands():
            group.add_command(build_click_command(registered), name=registered.name)  # type: ignore[attr-defined]
    else:
        _disable_everything_but_new_and_list(group)

    return group


def _disable_everything_but_new_and_list(group: click.Group) -> None:
    """Outside a project, only `new`, `list` and `--version` work (D-014); anything else gets a
    clear message instead of Click's generic "No such command"."""
    original_get_command = group.get_command

    def _get_command(ctx: click.Context, cmd_name: str) -> click.Command | None:
        found = original_get_command(ctx, cmd_name)
        if found is not None:
            return found

        def _unavailable(**_kwargs: Any) -> None:
            click.echo(
                f'"{cmd_name}" needs a Aso project (a directory with bootstrap/app.py). '
                "Run this inside a project, or create one with `aso new`.",
                err=True,
            )
            raise SystemExit(1)

        return click.Command(cmd_name, callback=_unavailable, add_help_option=False)

    group.get_command = _get_command  # type: ignore[method-assign]


def main() -> None:
    project_root = boot.find_project_root()
    if project_root is not None:
        target = boot.hand_over_target(project_root)
        if target is not None:
            os.environ[boot.HANDED_OVER_ENV] = "1"
            os.execv(str(target), [str(target), *sys.argv[1:]])
            return  # pragma: no cover - unreachable, os.execv replaces the process

    group = build_cli(project_root)
    group()
