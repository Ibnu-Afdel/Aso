from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
MODULES_ROOT = APP_ROOT / "modules"

FORBIDDEN_TOKENS = (
    "fastapi",
    "aiogram",
    "APIRouter",
    "Dispatcher",
)


def test_modules_are_framework_agnostic() -> None:
    violations: list[str] = []

    for path in MODULES_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()
        lower = content.lower()

        if "fastapi" in lower:
            violations.append(f"fastapi import/use found in module: app/{rel}")
        if "aiogram" in lower:
            violations.append(f"aiogram import/use found in module: app/{rel}")
        if "APIRouter" in content:
            violations.append(f"APIRouter found in module: app/{rel}")
        if "Dispatcher" in content:
            violations.append(f"Dispatcher found in module: app/{rel}")

    assert not violations, "\n".join(violations)
