"""The Typer CLI surface (D-014, S-4): colon names, grouped `--help`, `list`, `--version`, and
the outside-a-project surface."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from fastogram.console.cli import build_cli


def test_outside_a_project_only_new_list_and_version_work(runner: CliRunner, tmp_path: Path) -> None:
    group = build_cli(None)

    help_result = runner.invoke(group, ["--help"])
    assert help_result.exit_code == 0
    assert "new" in help_result.output
    assert "list" in help_result.output

    version_result = runner.invoke(group, ["--version"])
    assert version_result.exit_code == 0
    assert "FastoGram" in version_result.output

    # `--no-install` (so no `uv sync`/`npm install`/`fastogram migrate`) keeps this instant and
    # offline; the skeleton-copying logic itself is exercised here, the install/migrate steps by
    # `tests/skeleton/test_new_command.py`.
    target = tmp_path / "my-app"
    new_result = runner.invoke(group, ["new", str(target), "--no-install", "--no-npm", "--no-migrate"])
    assert new_result.exit_code == 0, new_result.output
    assert (target / "bootstrap" / "app.py").is_file()
    assert (target / "pyproject.toml").is_file()


def test_outside_a_project_other_commands_get_a_clear_message(runner: CliRunner) -> None:
    group = build_cli(None)
    result = runner.invoke(group, ["migrate"])
    assert result.exit_code == 1
    assert "project" in result.output.lower()


def test_help_groups_colon_commands_by_prefix(runner: CliRunner, cli_group) -> None:
    result = runner.invoke(cli_group, ["--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output
    assert "route:list" in result.output
    # The group name (before the colon) becomes its own rich_help_panel (S-4).
    assert "route" in result.output


def test_typo_gets_a_suggestion(runner: CliRunner, cli_group) -> None:
    result = runner.invoke(cli_group, ["route:lis"])
    assert result.exit_code != 0
    assert "route:list" in result.output


def test_list_command_lists_registered_commands(runner: CliRunner, cli_group) -> None:
    result = runner.invoke(cli_group, ["list"])
    assert result.exit_code == 0
    assert "route:list" in result.output
    assert "migrate" in result.output


def test_command_help_shows_its_description(runner: CliRunner, cli_group) -> None:
    result = runner.invoke(cli_group, ["route:list", "--help"])
    assert result.exit_code == 0
    assert "List all registered routes" in result.output
