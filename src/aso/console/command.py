"""`Command`: the base class every CLI command (framework or user) subclasses (T-50, D-029).

`signature`/`description` are class attributes parsed once (see `registry.register`).
`handle()` is called with `self._arguments`/`self._options` already populated (strings, or
lists of strings for `*` arguments/options -- callers convert types themselves, as in Laravel).
"""

from __future__ import annotations

from typing import Any

from aso.console.io import CommandIO


class Command:
    """Subclass this, set `signature`/`description`, and implement `async def handle(self) -> int`."""

    signature: str = ""
    description: str = ""

    def __init__(self, io: CommandIO, arguments: dict[str, Any], options: dict[str, Any]) -> None:
        self._io = io
        self._arguments = arguments
        self._options = options

    # ------------------------------------------------------------ input

    def argument(self, name: str) -> Any:
        return self._arguments.get(name)

    def option(self, name: str) -> Any:
        return self._options.get(name)

    # ------------------------------------------------------------ prompts

    async def ask(self, question: str, default: str | None = None) -> str:
        return await self._io.ask(question, default)

    async def secret(self, question: str) -> str:
        return await self._io.secret(question)

    async def confirm(self, question: str, default: bool = False) -> bool:
        return await self._io.confirm(question, default)

    # ------------------------------------------------------------ output

    def info(self, message: str) -> None:
        self._io.info(message)

    def comment(self, message: str) -> None:
        self._io.comment(message)

    def warn(self, message: str) -> None:
        self._io.warn(message)

    def error(self, message: str) -> None:
        self._io.error(message)

    def line(self, message: str = "") -> None:
        self._io.line(message)

    def new_line(self, count: int = 1) -> None:
        self._io.new_line(count)

    def table(self, headers: list[str], rows: list[list[Any]]) -> None:
        self._io.table(headers, rows)

    # ------------------------------------------------------------ programmatic invocation

    async def call(self, name: str, params: dict[str, Any] | None = None) -> int:
        """Run another command, sharing this command's terminal (T-50)."""
        from aso.console.registry import call as _call

        return await _call(name, params, io=self._io)

    # ------------------------------------------------------------ entry point

    async def handle(self) -> int:
        raise NotImplementedError(f"{type(self).__name__} must implement handle().")
