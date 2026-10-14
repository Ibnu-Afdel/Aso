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


async def test_hashed_column_is_hashed_before_it_is_persisted(db):
    # The transform runs in `process_bind_param` (T-31 "How it works"), i.e. at the SQL boundary,
    # not as a Python `__set__` hook -- so it is the *stored* value that is hashed, not
    # necessarily the in-memory attribute an unrefreshed instance still holds.
    class Account(Model):
        password: Mapped[str] = mapped_column(Hashed())

    await db.run_sync(Model.metadata.create_all)
    await Account.create(password="correct-horse")
    row = (await db.execute(Account.__table__.select())).mappings().one()
    assert row["password"] != "correct-horse"
    assert row["password"].startswith("$")

    from fastogram.security import hash

    assert hash.check("correct-horse", row["password"]) is True


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
