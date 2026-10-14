"""T-30 Transactions: the savepoint design proven by spike S-2, plus `DB.scope(fresh=)`."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import String
from sqlalchemy import exc as sa_exc

from fastogram.database import DB, Mapped, Model, mapped_column


def _user_model():
    class User(Model):
        email: Mapped[str] = mapped_column(String(100), unique=True)

    return User


# ---------------------------------------------------------------- the four S-2 cases named in T-30


async def test_write_after_read(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    await User.create(email="r@x.io")
    users = await User.all()
    u = await User.create(email="w@x.io")
    assert u.id and len(users) == 1
    async with DB.transaction():
        await User.create(email="t@x.io")
    assert len(await User.all()) == 3


async def test_failed_write_then_reading_an_unrelated_loaded_model(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    me = await User.create(email="me@x.io")
    other = await User.create(email="dupe@x.io")
    with pytest.raises(sa_exc.IntegrityError):
        await User.create(email="dupe@x.io")
    # the failed write only rolled back its own savepoint: both earlier objects stay readable.
    assert me.email == "me@x.io"
    assert other.email == "dupe@x.io"
    assert len(await User.all()) == 2


async def test_failed_transaction_then_reading_an_unrelated_loaded_model(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    me = await User.create(email="me2@x.io")
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            await User.create(email="gone@x.io")
            raise RuntimeError("boom")
    assert me.email == "me2@x.io"
    assert [u.email for u in await User.all()] == ["me2@x.io"]


async def test_nested_transaction_rollback_only_affects_the_inner_block(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    async with DB.transaction():
        await User.create(email="outer@x.io")
        try:
            async with DB.transaction():
                await User.create(email="inner@x.io")
                raise ValueError
        except ValueError:
            pass
        await User.create(email="outer2@x.io")
    assert sorted(u.email for u in await User.all()) == ["outer2@x.io", "outer@x.io"]


# ---------------------------------------------------------------- expiry on rollback


async def test_changed_model_is_expired_after_rollback_and_refresh_restores_it(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    u = await User.create(email="before@x.io")
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            u.email = "after@x.io"
            await u.save()
            raise RuntimeError
    await u.refresh()
    assert u.email == "before@x.io"


async def test_models_only_read_inside_a_rolled_back_transaction_are_unaffected(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    u = await User.create(email="unchanged@x.io")
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            _ = await User.find(u.id)  # read only, not changed
            raise RuntimeError
    assert u.email == "unchanged@x.io"  # must still be readable without a refresh


# ---------------------------------------------------------------- after_commit


async def test_after_commit_runs_only_on_commit(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    ran: list[str] = []
    async with DB.transaction():
        await User.create(email="ac@x.io")
        DB.after_commit(lambda: ran.append("yes"))
        assert ran == []
    assert ran == ["yes"]

    with pytest.raises(RuntimeError):
        async with DB.transaction():
            DB.after_commit(lambda: ran.append("no"))
            raise RuntimeError
    assert ran == ["yes"]


async def test_after_commit_callback_may_be_a_coroutine(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    ran: list[str] = []

    async def mark() -> None:
        ran.append("async-yes")

    async with DB.transaction():
        await User.create(email="ac2@x.io")
        DB.after_commit(mark)
    assert ran == ["async-yes"]


async def test_after_commit_outside_a_transaction_runs_immediately(db):
    ran: list[str] = []
    DB.after_commit(lambda: ran.append("immediate"))
    assert ran == ["immediate"]


async def test_after_commit_fires_only_after_the_outermost_block(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    ran: list[str] = []
    async with DB.transaction():
        await User.create(email="outer@x.io")
        async with DB.transaction():
            await User.create(email="inner@x.io")
            DB.after_commit(lambda: ran.append("inner-callback"))
        assert ran == [], "must not run until the OUTER block commits"
    assert ran == ["inner-callback"]


# ---------------------------------------------------------------- attempts= retry (callback form)


async def test_transaction_attempts_retries_on_retryable_error(db):
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            # fabricate a retryable OperationalError (deadlock-shaped) without needing a real
            # second connection to deadlock against.
            raise sa_exc.OperationalError(
                "simulated deadlock", None, Exception("deadlock detected"), connection_invalidated=False
            )
        await User.create(email="retried@x.io")
        return "ok"

    result = await DB.transaction(flaky, attempts=5)
    assert result == "ok"
    assert calls["n"] == 3
    assert await User.count() == 1


async def test_transaction_attempts_gives_up_on_a_non_retryable_error(db):
    await db.run_sync(Model.metadata.create_all)
    calls = {"n": 0}

    async def always_fails() -> None:
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        await DB.transaction(always_fails, attempts=5)
    assert calls["n"] == 1


async def test_transaction_attempts_exhausted_reraises_last_error(db):
    calls = {"n": 0}

    async def always_deadlocks() -> None:
        calls["n"] += 1
        raise sa_exc.OperationalError("simulated deadlock", None, Exception("deadlock detected"))

    with pytest.raises(sa_exc.OperationalError):
        await DB.transaction(always_deadlocks, attempts=3)
    assert calls["n"] == 3


async def test_transaction_context_manager_form_runs_the_block_once(db):
    """`async with DB.transaction():` cannot be replayed from the outside once it has raised
    (there is no way for a context manager to re-run the caller's `with`-suite) -- `attempts=`
    only has an effect on the callback form. This documents that known, intentional limitation
    (see `scope.transaction`'s docstring and the build report)."""
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    attempts = {"n": 0}
    with pytest.raises(ValueError):
        async with DB.transaction():
            attempts["n"] += 1
            await User.create(email="once@x.io")
            raise ValueError("boom")
    assert attempts["n"] == 1


# ---------------------------------------------------------------- DB.scope(fresh=)


async def test_db_scope_without_fresh_is_a_no_op_inside_an_existing_scope(db):
    outer = DB.session()
    async with DB.scope():
        assert DB.session() is outer


async def test_db_scope_fresh_gives_a_new_session(db):
    outer = DB.session()
    async with DB.scope(fresh=True):
        inner = DB.session()
        assert inner is not outer
    assert DB.session() is outer


async def test_db_scope_fresh_gives_a_task_its_own_scope(db):
    # Not `asyncio.gather()`: under the S-2 test-binding fixture every session (even a "fresh"
    # one) is bound to the *same* single test connection, so two genuinely concurrent fresh
    # scopes would interleave statements on one DBAPI connection and corrupt its transaction
    # state -- exactly the "do not run concurrent queries in one scope" rule T-30 itself warns
    # about (in production, `fresh=True` hands out a separate pooled connection, so this is a
    # test-fixture constraint, not a bug). `asyncio.create_task()` + an immediate `await`, as
    # S-2's own `test_job_runs_in_its_own_scope` does, still proves the scope/session are new.
    User = _user_model()
    await db.run_sync(Model.metadata.create_all)
    outer_session = DB.session()

    async def write_one(email: str) -> int:
        async with DB.scope(fresh=True):
            assert DB.session() is not outer_session
            user = await User.create(email=email)
            return user.id

    first_id = await asyncio.create_task(write_one("a@x.io"))
    second_id = await asyncio.create_task(write_one("b@x.io"))
    assert first_id != second_id
    assert sorted(u.email for u in await User.all()) == ["a@x.io", "b@x.io"]


async def test_db_session_is_the_current_scopes_async_session(db):
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(DB.session(), AsyncSession)
