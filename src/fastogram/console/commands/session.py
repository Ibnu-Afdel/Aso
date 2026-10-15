"""`session:prune` (T-18)."""

from __future__ import annotations

from fastogram.console.command import Command
from fastogram.console.registry import register


class SessionPruneCommand(Command):
    signature = "session:prune"
    description = "Delete expired session rows/entries"

    async def handle(self) -> int:
        from fastogram.session import prune_sessions

        count = await prune_sessions()
        self.info(f"Pruned {count} expired session(s).")
        return 0


def register_all() -> None:
    register(SessionPruneCommand, source="framework")
