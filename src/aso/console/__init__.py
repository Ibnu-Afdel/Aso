"""CLI and scheduler (T-50, T-45): `from aso.console import Command, call, call_output, command, schedule`.

```python
from aso.console import Command

class SendReport(Command):
    signature = "report:send {user_id} {--queue : Dispatch as a background job}"
    description = "Send the weekly summary report to a user"

    async def handle(self) -> int:
        self.info(f"Sending report for user {self.argument('user_id')}...")
        return 0
```

The `aso` CLI (`aso.console.cli`) is one Typer app with artisan-style colon command
names (S-4); see `docs/guide/T-50-cli.md`.
"""

from __future__ import annotations

from aso.console.command import Command
from aso.console.registry import CommandNotFound, call, call_output, command
from aso.console.schedule import Schedule, ScheduleEvent, schedule

__all__ = ["Command", "CommandNotFound", "Schedule", "ScheduleEvent", "call", "call_output", "command", "schedule"]
