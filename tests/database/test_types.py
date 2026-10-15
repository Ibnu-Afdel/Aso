"""T-31 column types: `Encrypted`, `Hashed` (over `fastogram.security`)."""

from __future__ import annotations

import pytest
from sqlalchemy import String

from fastogram.database import Encrypted, Hashed, Mapped, Model, mapped_column
from fastogram.security.keys import generate_key


@pytest.fixture(autouse=True)
def _app_key(monkeypatch):
    key = generate_key()
    monkeypatch.setattr("fastogram.config.config", lambda k, default=None: key if k == "app.key" else default)
    yield key


async def test_encrypted_column_round_trips_and_is_opaque_at_rest(db):
    from sqlalchemy import text

    class Secret(Model):
        value: Mapped[str] = mapped_column(Encrypted(String))

    await db.run_sync(Model.metadata.create_all)
    secret = await Secret.create(value="top-secret")
    assert secret.value == "top-secret"
    found = await Secret.find(secret.id)
    assert found.value == "top-secret"
    # `text()` bypasses the column's TypeDecorator, so this is the actual stored bytes.
    raw_value = (await db.execute(text(f"select value from {Secret.__tablename__}"))).scalar_one()
    assert raw_value != "top-secret"


async def test_hashed_column_hashes_on_assignment(db):
    # The transform runs on attribute assignment (Laravel's `hashed` cast), so the in-memory
    # attribute is already hashed, not just the value eventually written to the row.
    class Account(Model):
        password: Mapped[str] = mapped_column(Hashed())

    await db.run_sync(Model.metadata.create_all)

    account = Account(password="correct-horse")
    assert account.password != "correct-horse"
    assert account.password.startswith("$")

    from fastogram.security import hash

    assert hash.check("correct-horse", account.password) is True

    await account.save()
    row = (await db.execute(Account.__table__.select())).mappings().one()
    assert row["password"] == account.password


async def test_hashed_column_does_not_double_hash_an_already_hashed_value(db):
    class Account(Model):
        password: Mapped[str] = mapped_column(Hashed())

    await db.run_sync(Model.metadata.create_all)
    created = await Account.create(password="correct-horse")
    first_hash = (await db.execute(Account.__table__.select())).mappings().one()["password"]

    # Assigning the already-hashed value back (e.g. re-saving a loaded row unchanged) must not
    # hash it a second time.
    created.password = first_hash
    await created.save()
    second_row = (await db.execute(Account.__table__.select())).mappings().one()
    assert second_row["password"] == first_hash
