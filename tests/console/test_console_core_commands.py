"""`serve`, `dev`, `route:list`, `key:generate`, `env`, `about` (T-50, T-02, T-07).

`serve`/`dev` are tested by inspecting the command lines they would run, never by actually
starting a server (BUILD.md)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from fastogram.console.commands.core import build_dev_commands, build_serve_argv


def test_build_serve_argv_uses_uvicorn_factory() -> None:
    argv = build_serve_argv("0.0.0.0", 9000)
    assert argv[:3] == ["uvicorn", "bootstrap.app:create_app", "--factory"]
    assert "--host" in argv and "0.0.0.0" in argv
    assert "--port" in argv and "9000" in argv


def test_build_dev_commands_runs_uvicorn_and_vite() -> None:
    commands = build_dev_commands(port=8001, vite_port=5174, queue_enabled=False)
    assert commands["server"][:3] == ["uvicorn", "bootstrap.app:create_app", "--factory"]
    assert "--reload" in commands["server"]
    assert "8001" in commands["server"]
    assert commands["vite"][:3] == ["npm", "run", "dev"]
    assert "5174" in commands["vite"]
    assert "queue" not in commands


def test_build_dev_commands_adds_a_queue_worker_when_enabled() -> None:
    commands = build_dev_commands(queue_enabled=True)
    assert "queue:work" in commands["queue"]


def test_find_free_port_skips_a_port_already_in_use() -> None:
    import socket

    from fastogram.console.commands.core import find_free_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        chosen = find_free_port(port)
        assert chosen is not None and chosen != port
        assert find_free_port(port, taken={chosen}) not in (port, chosen)


def test_serve_falls_back_to_the_next_free_port(cli_group, runner: CliRunner, monkeypatch) -> None:
    import socket
    import subprocess

    calls: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(subprocess, "call", lambda argv, cwd=None, env=None: calls.append((argv, env)) or 0)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        result = runner.invoke(cli_group, ["serve", "--port", str(port)])
    assert result.exit_code == 0, result.output
    assert "in use; using" in result.output
    argv, env = calls[0]
    chosen = argv[argv.index("--port") + 1]
    assert chosen != str(port)
    assert env["APP_URL"].endswith(f":{chosen}")


def test_app_url_for_port_swaps_only_the_port() -> None:
    from fastogram.console.commands.core import app_url_for_port

    assert app_url_for_port("http://localhost:8000", 8001) == "http://localhost:8001"
    assert app_url_for_port("https://myapp.test", 8443) == "https://myapp.test:8443"


def test_route_list_shows_registered_routes(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["route:list"])
    assert result.exit_code == 0
    assert "welcome" in result.output
    assert "/" in result.output


def test_route_list_json_output(cli_group, runner: CliRunner) -> None:
    import json

    result = runner.invoke(cli_group, ["route:list", "--json"])
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert any(r["name"] == "welcome" for r in rows)


def test_route_list_filters_by_method(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["route:list", "--method=POST"])
    assert result.exit_code == 0
    assert "welcome" not in result.output


def test_key_generate_show_prints_without_writing_env(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["key:generate", "--show"])
    assert result.exit_code == 0
    assert result.output.strip().startswith("base64:")
    assert not (console_app_dir / ".env").exists()


def test_key_generate_writes_app_key_into_env(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["key:generate"])
    assert result.exit_code == 0
    env_path = console_app_dir / ".env"
    assert env_path.exists()
    content = env_path.read_text()
    assert "APP_KEY=base64:" in content


def test_key_generate_replaces_an_existing_app_key(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    env_path = console_app_dir / ".env"
    env_path.write_text("APP_NAME=Test\nAPP_KEY=base64:old\n")
    runner.invoke(cli_group, ["key:generate"])
    content = env_path.read_text()
    assert "APP_KEY=base64:old" not in content
    assert content.count("APP_KEY=") == 1
    assert "APP_NAME=Test" in content


def test_env_command_prints_the_current_environment(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["env"])
    assert result.exit_code == 0
    assert result.output.strip() == "testing"


def test_about_command_prints_a_summary_table(cli_group, runner: CliRunner) -> None:
    result = runner.invoke(cli_group, ["about"])
    assert result.exit_code == 0
    assert "Environment" in result.output
    assert "testing" in result.output
