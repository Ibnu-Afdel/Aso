"""T-55: `aso test --filter --parallel --coverage --bail` flag translation.

Inspects the argv `build_pytest_argv()` would hand to `pytest`, never starts a real subprocess
(BUILD.md: `serve`/`dev` are tested the same way in `tests/console/test_console_core_commands.py`).
"""

from __future__ import annotations

from aso.console.commands.test import TestCommand, build_pytest_argv
from aso.console.registry import reset_registry


def test_no_flags_passes_through_bare_args() -> None:
    assert build_pytest_argv(["tests/feature/test_home.py"]) == ["tests/feature/test_home.py"]


def test_filter_translates_to_dash_k() -> None:
    assert build_pytest_argv(filter_="auth") == ["-k", "auth"]


def test_parallel_translates_to_dash_n_auto() -> None:
    assert build_pytest_argv(parallel=True) == ["-n", "auto"]


def test_coverage_translates_to_cov_flags() -> None:
    assert build_pytest_argv(coverage=True) == ["--cov=app", "--cov-report=term-missing"]


def test_bail_translates_to_dash_x() -> None:
    assert build_pytest_argv(bail=True) == ["-x"]


def test_all_flags_combine_in_order() -> None:
    argv = build_pytest_argv(["tests/feature"], filter_="home", parallel=True, coverage=True, bail=True)
    assert argv == ["tests/feature", "-k", "home", "-n", "auto", "--cov=app", "--cov-report=term-missing", "-x"]


def test_register_all_registers_the_test_command() -> None:
    import aso.console.commands.test as test_module
    from aso.console.io import CommandIO
    from aso.console.registry import get

    reset_registry(keep="none")
    try:
        test_module.register_all()
        registered = get("test")
        assert registered is not None
        assert registered.name == "test"
        command = registered.factory(CommandIO(), {}, {})
        assert isinstance(command, TestCommand)
    finally:
        reset_registry(keep="none")
