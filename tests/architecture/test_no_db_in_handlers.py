from pathlib import Path
import re


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
HANDLERS_ROOT = APP_ROOT / "bot" / "handlers"

FORBIDDEN_TOKENS = (
    "SessionLocal",
    "async_session_maker",
    "Repository(",
    "select(",
    "engine",
)

SERVICE_INSTANTIATION_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]*Service\(")


def test_no_db_in_handlers() -> None:
    violations: list[str] = []

    for path in HANDLERS_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()

        for token in FORBIDDEN_TOKENS:
            if token in content:
                violations.append(f"{token} used inside handler: app/{rel}")

        if SERVICE_INSTANTIATION_PATTERN.search(content):
            violations.append(f"Service instantiated inside handler: app/{rel}")

    assert not violations, "\n".join(violations)
