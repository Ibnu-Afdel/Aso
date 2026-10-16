"""Terminal I/O for `Command` (T-50): coloured output helpers and the interactive prompts.

Prompts run in a worker thread (`asyncio.to_thread`) so they never block other tasks; with
`--no-interaction` (or when stdin is not a terminal) they return their default, or raise when
there is none.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from rich.console import Console
from rich.table import Table


class CommandIO:
    """Wraps a `rich.Console`. `call()` gives commands a buffer instead of real stdout."""

    def __init__(self, console: Console | None = None, *, no_interaction: bool = False) -> None:
        # `markup=False`: command output routinely interpolates file paths, URLs (`[::1]`),
        # keys and user data, none of which should be parsed as Rich markup (a stray `[...]`
        # raises `rich.errors.MarkupError` instead of just printing literally).
        self.console = console or Console(markup=False)
        self.no_interaction = no_interaction

    # ------------------------------------------------------------ output

    def info(self, message: str) -> None:
        self.console.print(message, style="green")

    def comment(self, message: str) -> None:
        self.console.print(message, style="yellow")

    def warn(self, message: str) -> None:
        self.console.print(message, style="yellow")

    def error(self, message: str) -> None:
        self.console.print(message, style="bold red")

    def line(self, message: str = "") -> None:
        self.console.print(message)

    def new_line(self, count: int = 1) -> None:
        for _ in range(count):
            self.console.print()

    def table(self, headers: list[str], rows: list[list[Any]]) -> None:
        t = Table()
        for header in headers:
            t.add_column(str(header))
        for row in rows:
            t.add_row(*[str(cell) for cell in row])
        self.console.print(t)

    # ------------------------------------------------------------ input

    async def ask(self, question: str, default: str | None = None) -> str:
        if self.no_interaction or not sys.stdin.isatty():
            if default is None:
                raise RuntimeError(f"Cannot prompt for {question!r} with --no-interaction and no default.")
            return default
        return await asyncio.to_thread(self._prompt, question, default)

    async def secret(self, question: str) -> str:
        if self.no_interaction or not sys.stdin.isatty():
            raise RuntimeError(f"Cannot prompt for {question!r} with --no-interaction.")
        import getpass

        return await asyncio.to_thread(getpass.getpass, f"{question} ")

    async def confirm(self, question: str, default: bool = False) -> bool:
        if self.no_interaction or not sys.stdin.isatty():
            return default
        suffix = "[Y/n]" if default else "[y/n]"
        answer = await asyncio.to_thread(self._prompt, f"{question} {suffix}", "y" if default else "n")
        return answer.strip().lower() in ("y", "yes")

    def _prompt(self, question: str, default: str | None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{question}{suffix} ")
        return value or (default or "")
