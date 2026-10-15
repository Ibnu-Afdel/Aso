"""Framework commands, one module per group (T-50). `register_framework_commands()` registers
every one of them into `fastogram.console.registry` -- generators (`make:controller`,
`make:model`, ...), factories/seeders and `fastogram new`/`doctor` plug in here the same way,
as their own module with its own `register_all()` (the next task)."""

from __future__ import annotations

from fastogram.console.commands import core, db, key, migrate, queue, route, schedule, session, storage

_MODULES = (core, key, route, db, session, storage, queue, migrate, schedule)


def register_framework_commands() -> None:
    """Idempotent: each module's `register_all()` just overwrites its own dict entries, so
    calling this on every `boot_console()` is cheap and safe even after a test's
    `reset_registry(keep="none")` has cleared everything, including framework commands."""
    for module in _MODULES:
        module.register_all()
