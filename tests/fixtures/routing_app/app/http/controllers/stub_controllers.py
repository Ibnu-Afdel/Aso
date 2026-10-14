"""Tiny controllers for resource-registration edge cases (T-10): `api_resource` excludes
`create`/`edit` even when defined; a plain `resource()` only registers actions the controller
actually defines."""

from __future__ import annotations

from fastogram.http import Controller


class WidgetController(Controller):
    async def index(self):
        return {"widgets": []}

    async def create(self):
        return {"should": "not be registered"}

    async def store(self):
        return {"stored": True}

    async def show(self, widget: int):
        return {"widget": widget}

    async def edit(self, widget: int):
        return {"should": "not be registered"}

    async def update(self, widget: int):
        return {"updated": widget}

    async def destroy(self, widget: int):
        return {"deleted": widget}


class ArchiveController(Controller):
    """Only `index` and `show` are defined: `update`/`destroy`/etc. must not be registered."""

    async def index(self):
        return {"archives": []}

    async def show(self, archive: int):
        return {"archive": archive}
