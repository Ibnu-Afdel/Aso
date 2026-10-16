"""Global installer vs project copy (D-014, T-02): `find_project_root`, `hand_over_target`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aso.console import boot


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "bootstrap").mkdir()
    (tmp_path / "bootstrap" / "app.py").write_text("def create_app():\n    pass\n")
    return tmp_path


def test_find_project_root_from_cwd(project: Path) -> None:
    assert boot.find_project_root(project) == project


def test_find_project_root_from_a_nested_directory(project: Path) -> None:
    nested = project / "app" / "http"
    nested.mkdir(parents=True)
    assert boot.find_project_root(nested) == project


def test_find_project_root_returns_none_outside_any_project(tmp_path: Path) -> None:
    assert boot.find_project_root(tmp_path) is None


def test_hand_over_target_is_none_without_a_project_venv(project: Path) -> None:
    assert boot.hand_over_target(project) is None


def test_hand_over_target_points_at_the_projects_own_copy(project: Path) -> None:
    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    aso_bin = venv_bin / "aso"
    aso_bin.write_text("#!/bin/sh\n")
    aso_bin.chmod(0o755)

    assert boot.hand_over_target(project) == aso_bin


def test_hand_over_target_respects_the_opt_out_env_var(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "aso").write_text("#!/bin/sh\n")

    monkeypatch.setenv(boot.NO_HANDOVER_ENV, "1")
    assert boot.hand_over_target(project) is None


def test_hand_over_target_is_none_once_already_handed_over(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "aso").write_text("#!/bin/sh\n")

    monkeypatch.setenv(boot.HANDED_OVER_ENV, "1")
    assert boot.hand_over_target(project) is None


def test_hand_over_target_is_none_when_we_are_already_that_copy(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    aso_bin = venv_bin / "aso"
    aso_bin.write_text("#!/bin/sh\n")

    monkeypatch.setattr(sys, "argv", [str(aso_bin), "migrate"])
    assert boot.hand_over_target(project) is None
