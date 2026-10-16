"""`Command`, `call()`, `call_output()` (T-50)."""

from __future__ import annotations

import pytest

from aso.console import Command, call, call_output, command
from aso.console.registry import CommandNotFound, register, reset_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    reset_registry()


class GreetCommand(Command):
    signature = "greet:hello {name} {--loud}"
    description = "Greet someone"

    async def handle(self) -> int:
        name = self.argument("name")
        if self.option("loud"):
            self.info(f"HELLO {name.upper()}!")
        else:
            self.line(f"Hello, {name}.")
        return 0


class FailingCommand(Command):
    signature = "greet:fail"
    description = "Always fails"

    async def handle(self) -> int:
        self.error("nope")
        return 1


async def test_call_runs_a_registered_command_and_returns_its_exit_code() -> None:
    register(GreetCommand)
    exit_code = await call("greet:hello", {"name": "Ada"})
    assert exit_code == 0
    assert "Hello, Ada." in call_output()


async def test_call_passes_options_with_the_dash_dash_prefix() -> None:
    register(GreetCommand)
    await call("greet:hello", {"name": "Ada", "--loud": True})
    assert "HELLO ADA!" in call_output()


async def test_call_nonzero_exit_code_is_returned() -> None:
    register(FailingCommand)
    exit_code = await call("greet:fail")
    assert exit_code == 1
    assert "nope" in call_output()


async def test_call_unknown_command_raises() -> None:
    with pytest.raises(CommandNotFound):
        await call("does:not-exist")


async def test_call_missing_required_argument_raises() -> None:
    register(GreetCommand)
    with pytest.raises(ValueError, match="name"):
        await call("greet:hello")


async def test_command_decorator_registers_a_closure_command() -> None:
    @command("ping", "Respond pong")
    def _ping(self: Command) -> int:
        self.info("pong")
        return 0

    exit_code = await call("ping")
    assert exit_code == 0
    assert "pong" in call_output()


async def test_closure_command_may_be_async() -> None:
    @command("ping-async")
    async def _ping_async(self: Command) -> int:
        self.info("pong-async")
        return 0

    exit_code = await call("ping-async")
    assert exit_code == 0
    assert "pong-async" in call_output()


async def test_argument_and_option_defaults_are_applied() -> None:
    class WithDefaults(Command):
        signature = "greet:default {name=World} {--shout=quiet}"
        description = ""

        async def handle(self) -> int:
            self.line(f"{self.argument('name')}/{self.option('shout')}")
            return 0

    register(WithDefaults)
    await call("greet:default")
    assert "World/quiet" in call_output()
