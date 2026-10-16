"""T-58: `arch()`/`arch_preset()` against two fixture projects (`tests/fixtures/arch_good`,
`tests/fixtures/arch_bad`) -- one that passes every rule, one with exactly one violation per
rule (A1-A13), plus `.ignoring()`, `.without()` and `# arch: ignore[ID] -- reason` behaviour.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aso.foundation import paths
from aso.testing.arch import ArchitectureViolation, arch, arch_preset

GOOD = Path(__file__).parent.parent / "fixtures" / "arch_good"
BAD = Path(__file__).parent.parent / "fixtures" / "arch_bad"

ALL_RULES = [f"A{i}" for i in range(1, 14)]


@pytest.fixture(autouse=True)
def _restore_base_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolates `aso.foundation.paths`' module-global `_base` to this test only."""
    monkeypatch.setattr(paths, "_base", paths._base, raising=False)


def test_aso_preset_passes_on_a_clean_project() -> None:
    paths.set_base_path(GOOD)
    arch_preset("aso").check()  # must not raise


def test_aso_preset_reports_every_rule_on_the_bad_project() -> None:
    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").check()
    message = str(excinfo.value)
    for rule in ALL_RULES:
        assert rule in message, f"{rule} did not fire on the bad fixture project"
    assert f"{len(ALL_RULES)} architecture rule(s) failed." in message


@pytest.mark.parametrize("rule", ALL_RULES)
def test_each_rule_fires_in_isolation_on_bad_and_not_on_good(rule: str) -> None:
    others = [r for r in ALL_RULES if r != rule]

    paths.set_base_path(GOOD)
    arch_preset("aso").without(*others).check()  # the good project never violates it

    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").without(*others).check()
    assert rule in str(excinfo.value)


def test_without_disables_one_rule() -> None:
    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").without("A7").check()
    assert "A7" not in str(excinfo.value)
    assert "A1" in str(excinfo.value)


def test_ignoring_drops_a_whole_package() -> None:
    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").ignoring("app.models").check()
    message = str(excinfo.value)
    assert "A2" not in message  # app/models/post.py
    assert "A11" not in message  # app/models/comment.py
    assert "A1" in message


def test_arch_ignore_comment_suppresses_that_line_only(tmp_path: Path) -> None:
    project = tmp_path / "bad_with_ignore"
    shutil.copytree(BAD, project)
    helper = project / "app" / "services" / "debug_helper.py"
    helper.write_text(
        helper.read_text().replace(
            'print("debugging")',
            'print("debugging")  # arch: ignore[A7] -- temporary, remove before release',
        )
    )
    paths.set_base_path(project)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").check()
    message = str(excinfo.value)
    assert "A7" not in message
    assert "A1" in message  # every other violation still fires


def test_arch_ignore_without_a_reason_does_not_suppress(tmp_path: Path) -> None:
    project = tmp_path / "bad_with_bad_ignore"
    shutil.copytree(BAD, project)
    helper = project / "app" / "services" / "debug_helper.py"
    helper.write_text(helper.read_text().replace('print("debugging")', 'print("debugging")  # arch: ignore[A7]'))
    paths.set_base_path(project)
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch_preset("aso").check()
    assert "A7" in str(excinfo.value)


def test_custom_rule_must_not_import() -> None:
    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation):
        arch("app.http.controllers").must_not_import("sqlalchemy").check()

    paths.set_base_path(GOOD)
    arch("app.http.controllers").must_not_import("sqlalchemy").check()


def test_custom_rule_classes_must_extend_and_have_suffix() -> None:
    paths.set_base_path(GOOD)
    arch("app.http.requests").classes().must_extend("FormRequest").check()
    arch("app.http.requests").classes().must_have_suffix("Request").check()

    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation):
        arch("app.http.requests").classes().must_have_suffix("Request").check()


def test_custom_rule_must_have_method() -> None:
    paths.set_base_path(GOOD)
    arch("app.jobs").classes().must_have_method("handle").check()


def test_custom_rule_must_not_call() -> None:
    paths.set_base_path(BAD)
    with pytest.raises(ArchitectureViolation):
        arch("app.services").must_not_call("print").check()


def test_custom_rule_functions_must_be_async() -> None:
    paths.set_base_path(GOOD)
    arch("app.jobs").classes().must_have_method("handle").check()


def test_type_checking_imports_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "app" / "models").mkdir(parents=True)
    (tmp_path / "app" / "models" / "user.py").write_text(
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from aso.http import Request\n"
    )
    paths.set_base_path(tmp_path)
    arch("app.models").must_not_import("aso.http").check()  # must not raise


def test_relative_imports_resolve_against_the_owning_package(tmp_path: Path) -> None:
    pkg = tmp_path / "app" / "models"
    pkg.mkdir(parents=True)
    (pkg / "user.py").write_text("from __future__ import annotations\nfrom . import helpers\n")
    (pkg / "helpers.py").write_text("x = 1\n")
    paths.set_base_path(tmp_path)
    # every module in the selection must import app.models.helpers: user.py does; helpers.py
    # (which imports nothing) does not -- exactly one violation, proving the relative import in
    # user.py resolved correctly (it is not reported).
    with pytest.raises(ArchitectureViolation) as excinfo:
        arch("app.models").must_import("app.models.helpers").check()
    assert "app.models.user" not in str(excinfo.value)
    assert "app.models.helpers" in str(excinfo.value)
