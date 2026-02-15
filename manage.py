#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"
ALEMBIC_INI = ROOT_DIR / "alembic.ini"
DOCKER_ENV_FILE = ROOT_DIR / "docker" / ".env"
DOCKER_COMPOSE_FILE = ROOT_DIR / "docker" / "docker-compose.yml"


def _ensure_uv() -> None:
    if shutil.which("uv") is None:
        raise SystemExit("uv is not installed or not in PATH.")


def _run(cmd: list[str], check: bool = True, cwd: Path | None = None) -> int:
    proc = subprocess.run(cmd, cwd=cwd or ROOT_DIR)
    if check and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.returncode


def _can_bind(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _next_available_port(start_port: int, host: str = "127.0.0.1", max_tries: int = 100) -> int:
    port = start_port
    for _ in range(max_tries):
        if _can_bind(port, host=host):
            return port
        port += 1
    raise SystemExit(f"Could not find available port after {max_tries} tries from {start_port}.")


def _ensure_env() -> None:
    if not ENV_FILE.exists():
        if not ENV_EXAMPLE_FILE.exists():
            raise SystemExit(".env.example not found.")
        ENV_FILE.write_text(ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        print("Created .env from .env.example")


def cmd_setup(_: argparse.Namespace) -> None:
    _ensure_uv()
    _ensure_env()
    _run(["uv", "sync"])


def cmd_sync(_: argparse.Namespace) -> None:
    _ensure_uv()
    _run(["uv", "sync"])


def cmd_run(args: argparse.Namespace) -> None:
    _ensure_uv()
    port = args.port
    if args.port_auto and not _can_bind(port, host=args.host):
        port = _next_available_port(port, host=args.host)
        print(f"Port in use, using {port}")

    cmd = ["uv", "run", "uvicorn", "app.main:app", "--host", args.host, "--port", str(port)]
    if args.reload:
        cmd.append("--reload")
    _run(cmd)


def cmd_test(args: argparse.Namespace) -> None:
    _ensure_uv()
    _run(["uv", "run", "python", "-m", "pytest", *args.pytest_args])


def cmd_lint(args: argparse.Namespace) -> None:
    _ensure_uv()
    cmd = ["uv", "run", "python", "-m", "ruff", "check", "app", "tests"]
    if args.fix:
        cmd.append("--fix")
    _run(cmd)


def cmd_format(args: argparse.Namespace) -> None:
    _ensure_uv()
    cmd = ["uv", "run", "python", "-m", "ruff", "format", "app", "tests"]
    if args.check:
        cmd.append("--check")
    _run(cmd)


def _import_check() -> None:
    _run(["uv", "run", "python", "-c", "import app.main"])


def cmd_check(_: argparse.Namespace) -> None:
    _ensure_uv()
    cmd_format(argparse.Namespace(check=True))
    cmd_lint(argparse.Namespace(fix=False))
    _import_check()
    cmd_test(argparse.Namespace(pytest_args=[]))


def cmd_shell(_: argparse.Namespace) -> None:
    _ensure_uv()
    _run(["uv", "run", "ipython"])


def cmd_doctor(args: argparse.Namespace) -> None:
    _ensure_uv()
    if not ENV_FILE.exists():
        raise SystemExit(".env is missing. Run: python manage.py setup")

    _import_check()
    _run(["uv", "run", "alembic", "-c", str(ALEMBIC_INI), "heads"])
    if args.with_current:
        _run(["uv", "run", "alembic", "-c", str(ALEMBIC_INI), "current"])
    print("Doctor checks passed.")


def cmd_make_module(args: argparse.Namespace) -> None:
    _ensure_uv()
    cmd = ["uv", "run", "python", "-m", "app.cli", "make-module", args.name]
    if args.force:
        cmd.append("--force")
    _run(cmd)


def cmd_make_model(args: argparse.Namespace) -> None:
    cmd_make_module(args)


def cmd_migrate(_: argparse.Namespace) -> None:
    _ensure_uv()
    _run(["uv", "run", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"])


def cmd_migrate_fresh(args: argparse.Namespace) -> None:
    _ensure_uv()
    if not args.yes:
        raise SystemExit("migrate-fresh is destructive. Re-run with --yes.")

    drop_script = (
        "import asyncio;"
        "from app.core.db import Base, engine;"
        "async def _drop():\n"
        "  async with engine.begin() as conn:\n"
        "    await conn.run_sync(Base.metadata.drop_all)\n"
        "asyncio.run(_drop())"
    )
    _run(["uv", "run", "python", "-c", drop_script])
    cmd_migrate(argparse.Namespace())


def cmd_downgrade(args: argparse.Namespace) -> None:
    _ensure_uv()
    _run(["uv", "run", "alembic", "-c", str(ALEMBIC_INI), "downgrade", args.revision])


def cmd_makemigration(args: argparse.Namespace) -> None:
    _ensure_uv()
    _run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            "revision",
            "--autogenerate",
            "-m",
            args.message,
        ]
    )


def cmd_webhook(args: argparse.Namespace) -> None:
    _ensure_uv()
    cmd = ["uv", "run", "python", "-m", "scripts.set_webhook"]
    if args.delete:
        cmd.append("--delete")
        cmd.append("--drop-pending-updates")
    _run(cmd)


def _ensure_docker_env() -> None:
    if not DOCKER_ENV_FILE.exists() and ENV_FILE.exists():
        DOCKER_ENV_FILE.write_text(ENV_FILE.read_text(encoding="utf-8"), encoding="utf-8")


def cmd_docker_up(_: argparse.Namespace) -> None:
    _ensure_docker_env()
    _run(["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "--build"])


def cmd_docker_down(_: argparse.Namespace) -> None:
    _run(["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE), "down"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project management CLI for FastGram.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup")
    p_setup.set_defaults(func=cmd_setup)

    p_sync = sub.add_parser("sync")
    p_sync.set_defaults(func=cmd_sync)

    p_run = sub.add_parser("run")
    p_run.add_argument("--host", default="127.0.0.1")
    p_run.add_argument("--port", type=int, default=8000)
    p_run.add_argument("--reload", action="store_true")
    p_run.add_argument("--port-auto", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_test = sub.add_parser("test")
    p_test.add_argument("pytest_args", nargs=argparse.REMAINDER)
    p_test.set_defaults(func=cmd_test)

    p_lint = sub.add_parser("lint")
    p_lint.add_argument("--fix", action="store_true")
    p_lint.set_defaults(func=cmd_lint)

    p_format = sub.add_parser("format")
    p_format.add_argument("--check", action="store_true")
    p_format.set_defaults(func=cmd_format)

    p_check = sub.add_parser("check")
    p_check.set_defaults(func=cmd_check)

    p_shell = sub.add_parser("shell")
    p_shell.set_defaults(func=cmd_shell)

    p_doctor = sub.add_parser("doctor")
    p_doctor.add_argument("--with-current", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_make = sub.add_parser("make")
    make_sub = p_make.add_subparsers(dest="make_command", required=True)
    p_make_module = make_sub.add_parser("module")
    p_make_module.add_argument("name")
    p_make_module.add_argument("--force", action="store_true")
    p_make_module.set_defaults(func=cmd_make_module)
    p_make_model = make_sub.add_parser("model")
    p_make_model.add_argument("name")
    p_make_model.add_argument("--force", action="store_true")
    p_make_model.set_defaults(func=cmd_make_model)

    p_migrate = sub.add_parser("migrate")
    p_migrate.set_defaults(func=cmd_migrate)

    p_migrate_fresh = sub.add_parser("migrate-fresh")
    p_migrate_fresh.add_argument("--yes", action="store_true")
    p_migrate_fresh.set_defaults(func=cmd_migrate_fresh)

    p_downgrade = sub.add_parser("downgrade")
    p_downgrade.add_argument("revision")
    p_downgrade.set_defaults(func=cmd_downgrade)

    p_makemigration = sub.add_parser("makemigration")
    p_makemigration.add_argument("-m", "--message", required=True)
    p_makemigration.set_defaults(func=cmd_makemigration)

    p_webhook = sub.add_parser("webhook")
    p_webhook.add_argument("--delete", action="store_true")
    p_webhook.set_defaults(func=cmd_webhook)

    p_docker_up = sub.add_parser("docker-up")
    p_docker_up.set_defaults(func=cmd_docker_up)

    p_docker_down = sub.add_parser("docker-down")
    p_docker_down.set_defaults(func=cmd_docker_down)

    return parser


def main() -> None:
    parser = _build_parser()
    args, unknown = parser.parse_known_args()
    if args.command == "test":
        args.pytest_args.extend(unknown)
    elif unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    args.func(args)


if __name__ == "__main__":
    main()
