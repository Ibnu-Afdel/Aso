"""Generators refuse to overwrite an existing file without `--force` (T-51)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner


def test_make_request_refuses_to_overwrite(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    first = runner.invoke(cli_group, ["make:request", "StorePostRequest"])
    assert first.exit_code == 0

    path = console_app_dir / "app" / "http" / "requests" / "store_post_request.py"
    path.write_text("# hand-edited\n")

    second = runner.invoke(cli_group, ["make:request", "StorePostRequest"])
    assert second.exit_code == 1
    assert "already exists" in second.output
    assert path.read_text() == "# hand-edited\n"  # untouched


def test_make_request_force_overwrites(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    path = console_app_dir / "app" / "http" / "requests" / "store_post_request.py"
    runner.invoke(cli_group, ["make:request", "StorePostRequest"])
    path.write_text("# hand-edited\n")

    result = runner.invoke(cli_group, ["make:request", "StorePostRequest", "--force"])
    assert result.exit_code == 0, result.output
    assert "class StorePostRequest(FormRequest):" in path.read_text()


def test_make_model_refuses_to_overwrite(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    first = runner.invoke(cli_group, ["make:model", "Widget"])
    assert first.exit_code == 0

    second = runner.invoke(cli_group, ["make:model", "Widget"])
    assert second.exit_code == 1
    assert "already exists" in second.output


def test_make_mail_refuses_to_overwrite_either_file(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:mail", "WelcomeMail"])
    result = runner.invoke(cli_group, ["make:mail", "WelcomeMail"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_make_page_refuses_to_overwrite(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["make:page", "posts/index"])
    result = runner.invoke(cli_group, ["make:page", "posts/index"])
    assert result.exit_code == 1
    assert "already exists" in result.output

    forced = runner.invoke(cli_group, ["make:page", "posts/index", "--force"])
    assert forced.exit_code == 0, forced.output
