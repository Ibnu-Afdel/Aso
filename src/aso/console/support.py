"""Small helpers shared by the `commands/*.py` modules."""

from __future__ import annotations

from aso.console.command import Command


async def guard_production(cmd: Command, *, action: str = "run this command") -> bool:
    """Laravel's destructive-command confirmation: in production, require `--force` or an
    interactive "yes". Returns `True` when the caller should proceed."""
    from aso.foundation.application import environment

    if environment() != "production":
        return True
    if cmd.option("force"):
        return True
    cmd.warn("Application In Production.")
    return await cmd.confirm(f"Are you sure you want to {action}?", default=False)
