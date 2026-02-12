from pathlib import Path
import re


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ROUTES_ROOT = APP_ROOT / "api" / "routes"

FORBIDDEN_TOKENS = (
    "SessionLocal",
    "Repository(",
    "engine",
)

SERVICE_INSTANTIATION_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]*Service\(")


def test_no_db_in_routes() -> None:
    violations: list[str] = []

    for path in ROUTES_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()

        for token in FORBIDDEN_TOKENS:
            if token in content:
                violations.append(f"{token} used inside route: app/{rel}")

        if SERVICE_INSTANTIATION_PATTERN.search(content):
            violations.append(f"Service instantiated inside route: app/{rel}")

    assert not violations, "\n".join(violations)
