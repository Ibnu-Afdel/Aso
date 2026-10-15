"""`fastogram test` (T-55): a thin wrapper around `pytest`.

`build_pytest_argv()` is a pure function so the flag translation can be unit-tested without
actually running pytest (`tests/testing/test_test_command.py`, mirroring how `core.py` tests
`build_serve_argv`/`build_dev_commands` -- BUILD.md: never start a real subprocess in a test)."""

from __future__ import annotations

import subprocess
import sys

from fastogram.console.command import Command
from fastogram.console.registry import register


def build_pytest_argv(
    args: list[str] | None = None,
    *,
    filter_: str | None = None,
    parallel: bool = False,
    coverage: bool = False,
    bail: bool = False,
) -> list[str]:
    """`fastogram test --filter --parallel --coverage --bail` -> the `pytest` argv (T-55)."""
    argv: list[str] = list(args or [])
    if filter_:
        argv += ["-k", filter_]
    if parallel:
        argv += ["-n", "auto"]
    if coverage:
        argv += ["--cov=app", "--cov-report=term-missing"]
    if bail:
        argv.append("-x")
    return argv


class TestCommand(Command):
    __test__ = False  # not a pytest test class, despite the name (it IS `fastogram test`)

    signature = (
        "test {args?* : pytest arguments (file paths, -k expressions, ...)} "
        "{--filter= : only run tests whose name matches this pattern (pytest -k)} "
        "{--parallel : run across CPU workers (pytest-xdist -n auto)} "
        "{--coverage : run with coverage (pytest --cov)} "
        "{--bail : stop on the first failure (pytest -x)}"
    )
    description = "Run the application's test suite"

    async def handle(self) -> int:
        argv = build_pytest_argv(
            self.argument("args"),
            filter_=self.option("filter"),
            parallel=bool(self.option("parallel")),
            coverage=bool(self.option("coverage")),
            bail=bool(self.option("bail")),
        )
        result = subprocess.run([sys.executable, "-m", "pytest", *argv])  # noqa: S603
        return result.returncode


def register_all() -> None:
    register(TestCommand, source="framework")
