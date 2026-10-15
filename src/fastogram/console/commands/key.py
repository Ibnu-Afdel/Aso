"""`key:generate` (T-40)."""

from __future__ import annotations

import re

from fastogram.console.command import Command
from fastogram.console.registry import register


class KeyGenerateCommand(Command):
    signature = "key:generate {--show : Display the key instead of modifying the .env file} {--force : Force the operation to run in production}"
    description = "Set the application key"

    async def handle(self) -> int:
        from fastogram.security.keys import generate_key

        key = generate_key()
        if self.option("show"):
            self.line(key)
            return 0

        from fastogram.foundation.application import environment
        from fastogram.foundation.paths import base_path

        if environment() == "production" and not self.option("force"):
            self.warn("Application In Production.")
            if not await self.confirm("Are you sure you want to run this command?", default=False):
                return 1

        env_path = base_path(".env")
        _write_app_key(env_path, key)
        self.info(f"Application key set successfully: {key}")
        return 0


def _write_app_key(env_path, key: str) -> None:
    pattern = re.compile(r"^APP_KEY=.*$", re.MULTILINE)
    if env_path.exists():
        content = env_path.read_text()
        if pattern.search(content):
            content = pattern.sub(f"APP_KEY={key}", content, count=1)
        else:
            content = content.rstrip("\n") + f"\nAPP_KEY={key}\n"
    else:
        content = f"APP_KEY={key}\n"
    env_path.write_text(content)


def register_all() -> None:
    register(KeyGenerateCommand, source="framework")
