from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ALLOWED_FILES = {
    (APP_ROOT / "core" / "db.py").resolve(),
    (APP_ROOT / "bootstrap" / "session_manager.py").resolve(),
}


def test_sessionlocal_usage_restricted() -> None:
    violations: list[str] = []

    for path in APP_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "SessionLocal(" not in content:
            continue

        if path.resolve() not in ALLOWED_FILES:
            rel = path.relative_to(APP_ROOT).as_posix()
            violations.append(f"SessionLocal used outside allowed files: app/{rel}")

    assert not violations, "\n".join(violations)
