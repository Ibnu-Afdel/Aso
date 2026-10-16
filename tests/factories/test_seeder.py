"""`Seeder`/`seed()` (T-36): `run()`, `call([...])`, and name-based resolution against
`database/seeders/<name>.py`."""

from __future__ import annotations

import pytest
from sqlalchemy import String

from aso.database import Mapped, Model, Seeder, mapped_column
from aso.database.seeder import seed


async def test_run_must_be_implemented():
    class EmptySeeder(Seeder):
        pass

    with pytest.raises(NotImplementedError):
        await EmptySeeder().run()


async def test_call_runs_each_seeder_in_order(db):
    class Note(Model):
        body: Mapped[str] = mapped_column(String(255))

    await db.run_sync(Model.metadata.create_all)
    order: list[str] = []

    class FirstSeeder(Seeder):
        async def run(self) -> None:
            order.append("first")
            await Note.create(body="first")

    class SecondSeeder(Seeder):
        async def run(self) -> None:
            order.append("second")
            await Note.create(body="second")

    class RootSeeder(Seeder):
        async def run(self) -> None:
            await self.call([FirstSeeder, SecondSeeder])

    await RootSeeder().run()
    assert order == ["first", "second"]
    assert await Note.count() == 2


async def test_seed_resolves_a_seeder_by_class_name(db, factories_app):
    """Uses the on-disk `tests/fixtures/factories_app` convention (`database/seeders/...`)."""
    import sys
    from pathlib import Path

    root = Path(__file__).parent.parent / "fixtures" / "factories_app"
    seeders_dir = root / "database" / "seeders"
    seeders_dir.mkdir(parents=True, exist_ok=True)
    (seeders_dir / "__init__.py").touch()
    (seeders_dir / "ping_seeder.py").write_text(
        "from aso.database import Seeder\n\n"
        "calls = []\n\n"
        "class PingSeeder(Seeder):\n"
        "    async def run(self) -> None:\n"
        "        calls.append('ran')\n"
    )
    sys.path.insert(0, str(root))
    try:
        await seed("PingSeeder")
        import database.seeders.ping_seeder as ping_module

        assert ping_module.calls == ["ran"]
    finally:
        sys.path.remove(str(root))
        import shutil

        shutil.rmtree(seeders_dir)
        for name in list(sys.modules):
            if name.startswith("database.seeders"):
                del sys.modules[name]


async def test_seed_raises_a_clear_error_when_the_seeder_is_missing(db):
    with pytest.raises(RuntimeError, match="NoSuchSeeder"):
        await seed("NoSuchSeeder")
