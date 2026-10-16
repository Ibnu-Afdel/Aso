"""`Seeder` and the `seed()` helper (T-36).

```python
class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        await self.call([PostSeeder])
```

`seed()` lives here (not in `aso.console`) so `aso.testing` (a later task) can import
and re-export it without a circular import back into `aso.database`.
"""

from __future__ import annotations

import re

__all__ = ["Seeder", "seed"]


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class Seeder:
    """Subclass this and implement `async def run(self)`."""

    async def run(self) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement async def run(self).")

    async def call(self, seeders: list[type[Seeder]]) -> None:
        """`await self.call([PostSeeder, CommentSeeder])`: run each seeder, in order."""
        for seeder_cls in seeders:
            await seeder_cls().run()


def _resolve(seeder: type[Seeder] | str | None) -> type[Seeder]:
    if seeder is None:
        return _import_by_name("DatabaseSeeder")
    if isinstance(seeder, str):
        return _import_by_name(seeder)
    return seeder


def _import_by_name(class_name: str) -> type[Seeder]:
    """`"PostSeeder"` -> `database.seeders.post_seeder.PostSeeder` (the same convention
    `make:seeder` uses to place the file, T-51)."""
    import importlib

    module_name = f"database.seeders.{_snake(class_name)}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f'Seeder "{class_name}" not found (expected database/seeders/{_snake(class_name)}.py).'
        ) from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise RuntimeError(f'Module "{module_name}" has no class "{class_name}".') from exc


async def seed(seeder: type[Seeder] | str | None = None) -> None:
    """Run a seeder: no argument runs `database/seeders/database_seeder.py`'s `DatabaseSeeder`;
    a class or its name (`"PostSeeder"`) runs that one instead. Used by `aso db:seed`
    (T-50) and, later, by `aso.testing`'s own `seed()` re-export (T-57)."""
    seeder_cls = _resolve(seeder)
    await seeder_cls().run()
