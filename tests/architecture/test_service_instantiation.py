from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
CONTAINER_FILE = APP_ROOT / "bootstrap" / "container.py"

FORBIDDEN_PATTERNS = (
    "= UserAppService(",
    "= HealthAppService(",
    "= TelegramWebhookAppService(",
)


def test_only_container_instantiates_app_services() -> None:
    violations: list[str] = []

    for path in APP_ROOT.rglob("*.py"):
        if path == CONTAINER_FILE:
            continue

        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()

        for pattern in FORBIDDEN_PATTERNS:
            if pattern in content:
                violations.append(f"{pattern} found outside container: app/{rel}")

    assert not violations, "\n".join(violations)
