"""`fastogram doctor` (T-61): pass/warn/fail lines and a non-zero exit on failure."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner


def test_doctor_reports_healthy_on_the_console_app_fixture(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "[PASS] Application key: configured" in result.output
    assert "[WARN]" in result.output  # no node_modules / build manifest in the fixture
    assert "Everything looks healthy!" in result.output


def test_doctor_fails_when_the_app_key_is_missing(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    from fastogram.config import set_config

    set_config("app.key", None)
    try:
        result = runner.invoke(cli_group, ["doctor"])
        assert result.exit_code == 1
        assert "[FAIL] Application key: not set" in result.output
        assert "Some checks failed." in result.output
    finally:
        set_config("app.key", "base64:dGVzdGluZy1rZXktdGVzdGluZy1rZXktMzJieXQ9")


def test_doctor_fails_when_migrations_are_pending(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    result = runner.invoke(cli_group, ["doctor"])
    assert result.exit_code == 1
    assert "[FAIL] Migrations: 1 pending" in result.output


def test_doctor_passes_once_migrations_are_applied(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:migration", "create posts table"])
    runner.invoke(cli_group, ["migrate"])
    result = runner.invoke(cli_group, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "[PASS] Migrations: up to date" in result.output
