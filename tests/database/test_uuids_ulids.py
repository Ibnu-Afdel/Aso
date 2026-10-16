"""T-31: `HasUuids` / `HasUlids` primary-key mixins."""

from __future__ import annotations

import uuid

from sqlalchemy import String

from aso.database import HasUlids, HasUuids, Mapped, Model, mapped_column


async def test_has_uuids_generates_a_uuid7_primary_key(db):
    class Invoice(HasUuids, Model):
        number: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    invoice = await Invoice.create(number="INV-1")
    assert isinstance(invoice.id, str)
    parsed = uuid.UUID(invoice.id)
    assert parsed.version == 7
    assert (await Invoice.find(invoice.id)).number == "INV-1"


async def test_has_uuids_ids_are_unique_and_ordered(db):
    class Invoice(HasUuids, Model):
        number: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    a = await Invoice.create(number="A")
    b = await Invoice.create(number="B")
    assert a.id != b.id
    assert a.id < b.id  # UUIDv7 is time-ordered


async def test_has_ulids_generates_a_26_char_ulid_primary_key(db):
    class Invoice(HasUlids, Model):
        number: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    invoice = await Invoice.create(number="INV-1")
    assert isinstance(invoice.id, str)
    assert len(invoice.id) == 26
    assert (await Invoice.find(invoice.id)).number == "INV-1"


async def test_has_ulids_ids_sort_lexicographically_by_time(db):
    class Invoice(HasUlids, Model):
        number: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    a = await Invoice.create(number="A")
    b = await Invoice.create(number="B")
    assert a.id != b.id
    assert a.id <= b.id
