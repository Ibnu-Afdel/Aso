"""`agents:update` (T-61): writes/refreshes the AGENTS.md section between
`<!-- aso:start -->`/`<!-- aso:end -->` markers."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def _cleanup_agents_md(console_app_dir: Path):
    path = console_app_dir / "AGENTS.md"
    try:
        yield
    finally:
        if path.exists():
            path.unlink()


def test_creates_agents_md_when_missing(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["agents:update"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "AGENTS.md"
    assert path.is_file()
    content = path.read_text()
    assert "<!-- aso:start -->" in content
    assert "<!-- aso:end -->" in content
    assert "# Instructions for AI Agents" in content
    assert "Generator First" in content
    assert "aso make:model Post" in content


def test_rerunning_replaces_only_the_marked_section(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    runner.invoke(cli_group, ["agents:update"])
    path = console_app_dir / "AGENTS.md"
    custom_note = "\n\n## Our team's own notes\nDon't touch the billing module.\n"
    path.write_text(path.read_text() + custom_note)

    result = runner.invoke(cli_group, ["agents:update"])
    assert result.exit_code == 0, result.output
    content = path.read_text()
    assert "Our team's own notes" in content
    assert content.count("<!-- aso:start -->") == 1


def test_refuses_to_overwrite_a_file_with_no_markers(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    path = console_app_dir / "AGENTS.md"
    path.write_text("# Our own hand-written notes, no markers here.\n")

    result = runner.invoke(cli_group, ["agents:update"])
    assert result.exit_code == 1
    assert "no <!-- aso:start/end --> markers" in result.output
    assert path.read_text() == "# Our own hand-written notes, no markers here.\n"


def test_force_overwrites_a_file_with_no_markers(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    path = console_app_dir / "AGENTS.md"
    path.write_text("# Our own hand-written notes, no markers here.\n")

    result = runner.invoke(cli_group, ["agents:update", "--force"])
    assert result.exit_code == 0, result.output
    assert "<!-- aso:start -->" in path.read_text()
