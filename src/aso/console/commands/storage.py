"""`storage:link` (T-43)."""

from __future__ import annotations

from aso.console.command import Command
from aso.console.registry import register


class StorageLinkCommand(Command):
    signature = "storage:link"
    description = 'Create the symbolic link from "public/storage" to "storage/app/public"'

    async def handle(self) -> int:
        from aso.storage import link_public_storage

        link = link_public_storage()
        self.info(f"The {link} link has been connected.")
        return 0


def register_all() -> None:
    register(StorageLinkCommand, source="framework")
