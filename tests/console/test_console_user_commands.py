"""User commands discovered from `app/console/commands/` and `@command(...)` closures in
`routes/console.py` (T-50)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner


def test_discovers_a_command_subclass_in_app_console_commands(console_app_dir: Path, runner: CliRunner) -> None:
    commands_dir = console_app_dir / "app" / "console" / "commands"
    custom = commands_dir / "send_report.py"
    custom.write_text(
        "from aso.console import Command\n\n"
        "class SendReport(Command):\n"
        '    signature = "report:send {user_id} {--queue : Dispatch as a background job}"\n'
        '    description = "Send the weekly summary report to a user"\n\n'
        "    async def handle(self) -> int:\n"
        '        self.info(f"Generating report for {self.argument(\'user_id\')}...")\n'
        "        if self.option('queue'):\n"
        '            self.line("Dispatching report job to queue...")\n'
        '        self.info("Report processed.")\n'
        "        return 0\n"
    )
    try:
        from aso.console.cli import build_cli

        group = build_cli(console_app_dir)

        help_result = runner.invoke(group, ["--help"])
        assert "report:send" in help_result.output

        result = runner.invoke(group, ["report:send", "42", "--queue"])
        assert result.exit_code == 0, result.output
        assert "Generating report for 42" in result.output
        assert "Dispatching report job to queue" in result.output
        assert "Report processed." in result.output
    finally:
        custom.unlink()


def test_command_call_from_test_suite(console_app_dir: Path) -> None:
    commands_dir = console_app_dir / "app" / "console" / "commands"
    custom = commands_dir / "send_report2.py"
    custom.write_text(
        "from aso.console import Command\n\n"
        "class SendReport2(Command):\n"
        '    signature = "report:send2 {user_id}"\n'
        '    description = ""\n\n'
        "    async def handle(self) -> int:\n"
        '        self.info("Report processed.")\n'
        "        return 0\n"
    )
    try:
        from aso.console.boot import boot_console
        from aso.console.registry import call, call_output

        boot_console(console_app_dir)
        import asyncio

        exit_code = asyncio.run(call("report:send2", {"user_id": 7}))
        assert exit_code == 0
        assert "Report processed." in call_output()
    finally:
        custom.unlink()


def test_command_decorator_in_routes_console(console_app_dir: Path, runner: CliRunner) -> None:
    console_route = console_app_dir / "routes" / "console.py"
    console_route.write_text(
        "from aso.console import command\n\n"
        '@command("ping:route", "Respond pong")\n'
        "def _ping(self):\n"
        '    self.info("pong")\n'
        "    return 0\n"
    )
    try:
        from aso.console.cli import build_cli

        group = build_cli(console_app_dir)
        result = runner.invoke(group, ["ping:route"])
        assert result.exit_code == 0
        assert "pong" in result.output
    finally:
        console_route.unlink()
