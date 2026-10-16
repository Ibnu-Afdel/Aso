"""T-30 DB: raw SQL helpers and the query listener."""

from __future__ import annotations

from sqlalchemy import String

from aso.database import DB, Mapped, Model, QueryExecuted, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        votes: Mapped[int] = mapped_column(default=0)

    return Post


async def test_select_returns_list_of_dicts(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=2)
    rows = await DB.select(f"select id, title from {Post.__tablename__} order by title")
    assert rows == [{"id": rows[0]["id"], "title": "A"}, {"id": rows[1]["id"], "title": "B"}]


async def test_select_one_returns_dict_or_none(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="A")
    row = await DB.select_one(f"select * from {Post.__tablename__} where id = :id", {"id": post.id})
    assert row["title"] == "A"
    assert await DB.select_one(f"select * from {Post.__tablename__} where id = :id", {"id": 999}) is None


async def test_scalar(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    count = await DB.scalar(f"select count(*) from {Post.__tablename__}")
    assert count == 2


async def test_insert_update_delete_affect_rows(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await DB.insert(f"insert into {Post.__tablename__} (title, votes) values (:t, :v)", {"t": "A", "v": 1})
    assert await Post.count() == 1

    affected = await DB.update(f"update {Post.__tablename__} set votes = 100 where title = :t", {"t": "A"})
    assert affected == 1
    assert (await Post.query().first()).votes == 100

    deleted = await DB.delete(f"delete from {Post.__tablename__} where title = :t", {"t": "A"})
    assert deleted == 1
    assert await Post.count() == 0


async def test_statement_runs_arbitrary_sql(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    result = await DB.statement(f"delete from {Post.__tablename__}")
    assert result is True
    assert await Post.count() == 0


async def test_listen_receives_query_executed_events(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    events: list[QueryExecuted] = []
    DB.listen(events.append)
    try:
        await Post.create(title="A")
        await Post.all()
    finally:
        from aso.database.db import _listeners

        _listeners.remove(events.append)
    assert events, "expected at least one QueryExecuted notification"
    sample = events[0]
    assert isinstance(sample.sql, str)
    assert isinstance(sample.bindings, dict)
    assert isinstance(sample.time_ms, float)
