"""`after_commit` (T-42): a job dispatched inside `DB.transaction()` waits for the commit."""

from __future__ import annotations

import _jobs

from aso.database.db import DB
from aso.database.scope import current_scope


class _AfterCommitJob(_jobs.EchoJob):
    after_commit = True


async def test_default_job_runs_immediately_even_inside_an_open_transaction(db):
    async with DB.transaction():
        await _jobs.EchoJob(value="now").dispatch()
        assert _jobs.calls, "after_commit defaults to False: dispatch() should run right away"


async def test_after_commit_job_waits_for_the_commit(db):
    session_id = id(current_scope().session())
    async with DB.transaction():
        await _AfterCommitJob(value="later").dispatch()
        assert _jobs.calls == [], "after_commit=True should defer until the transaction commits"
    assert _jobs.calls == [{"job": "echo", "value": "later", "session_id": session_id}]


async def test_after_commit_job_never_runs_if_the_transaction_rolls_back(db):
    class Boom(Exception):
        pass

    try:
        async with DB.transaction():
            await _AfterCommitJob(value="rolled-back").dispatch()
            raise Boom
    except Boom:
        pass
    assert _jobs.calls == []


async def test_after_commit_runs_immediately_with_no_open_transaction(db):
    session_id = id(current_scope().session())
    await _AfterCommitJob(value="no-txn").dispatch()
    assert _jobs.calls == [{"job": "echo", "value": "no-txn", "session_id": session_id}]
