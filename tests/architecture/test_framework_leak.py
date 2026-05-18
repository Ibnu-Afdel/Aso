from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
MODULES_ROOT = APP_ROOT / "modules"

FORBIDDEN_TOKENS = (
    "fastapi",
    "aiogram",
    "APIRouter",
    "Dispatcher",
)


_MSG = (
    "Modules must stay pure (no fastapi, aiogram, Telegram objects). "
    "Fix: move framework code to handlers or routes. See AGENTS.md."
)


def test_modules_are_framework_agnostic() -> None:
    violations: list[str] = []

    for path in MODULES_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(APP_ROOT).as_posix()
        lower = content.lower()

        if "fastapi" in lower:
            violations.append(f"app/{rel}: fastapi import/use. {_MSG}")
        if "aiogram" in lower:
            violations.append(f"app/{rel}: aiogram import/use. {_MSG}")
        if "APIRouter" in content:
            violations.append(f"app/{rel}: APIRouter. {_MSG}")
        if "Dispatcher" in content:
            violations.append(f"app/{rel}: Dispatcher. {_MSG}")

    assert not violations, (
        "Architecture violation: framework leak into modules.\n"
        + "\n".join(violations)
    )
