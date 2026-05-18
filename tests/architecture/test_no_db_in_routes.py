from pathlib import Path
import re


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
ROUTES_ROOT = APP_ROOT / "api" / "routes"

FORBIDDEN_TOKENS = (
    "SessionLocal",
    "get_session",
    "session_scope",
    "Repository(",
    "engine",
    "from app.core.db",
)

SERVICE_INSTANTIATION_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]*Service\(")


_MSG = (
    "Routes must not touch DB or instantiate services. "
    "Fix: use Depends(get_*_app_service), call them. See AGENTS.md."
)


def test_no_db_in_routes() -> None:
    violations: list[str] = []

    for path in ROUTES_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()

        for token in FORBIDDEN_TOKENS:
            if token in content:
                violations.append(
                    f"app/{rel}: '{token}' forbidden. {_MSG}"
                )

        if SERVICE_INSTANTIATION_PATTERN.search(content):
            violations.append(
                f"app/{rel}: Service instantiated directly. {_MSG}"
            )

    assert not violations, (
        "Architecture violation: DB or service instantiation in routes.\n"
        + "\n".join(violations)
    )
