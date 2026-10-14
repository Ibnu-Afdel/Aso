"""T-32 Querying: ordering, limiting, distinct, to_sql, from_statement, scopes."""

from __future__ import annotations

from sqlalchemy import String, select

from fastogram.database import Builder, Mapped, Model, mapped_column, scope


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        votes: Mapped[int] = mapped_column(default=0)

        @scope
        def published(cls, query: Builder) -> Builder:  # noqa: N805
            return query.where(cls.votes > 0)

    return Post


async def test_order_by_default_asc_and_desc(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="B", votes=2)
    await Post.create(title="A", votes=1)
    asc = await Post.order_by(Post.title).get()
    assert [p.title for p in asc] == ["A", "B"]
    desc = await Post.order_by(Post.votes, "desc").get()
    assert [p.title for p in desc] == ["B", "A"]


async def test_latest_and_oldest_use_created_at_by_default(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    first = await Post.create(title="first")
    second = await Post.create(title="second")
    assert (await Post.latest().first()).title == second.title
    assert (await Post.oldest().first()).title == first.title


async def test_latest_with_explicit_column(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=5)
    assert (await Post.latest(Post.votes).first()).title == "B"


async def test_reorder_drops_earlier_orderings(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="B", votes=1)
    await Post.create(title="A", votes=2)
    rows = await Post.latest().reorder(Post.title).get()
    assert [p.title for p in rows] == ["A", "B"]


async def test_take_and_skip_are_limit_offset_aliases(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    for i in range(5):
        await Post.create(title=str(i), votes=i)
    rows = await Post.order_by(Post.votes).skip(1).take(2).get()
    assert [p.title for p in rows] == ["1", "2"]


async def test_for_page(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    for i in range(10):
        await Post.create(title=str(i), votes=i)
    rows = await Post.order_by(Post.votes).for_page(2, 3).get()
    assert [p.title for p in rows] == ["3", "4", "5"]


async def test_in_random_order_returns_all_rows(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    for i in range(5):
        await Post.create(title=str(i))
    rows = await Post.in_random_order().get()
    assert {p.title for p in rows} == {"0", "1", "2", "3", "4"}


async def test_distinct(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="A", votes=2)
    titles = await Post.distinct().pluck(Post.title)
    assert sorted(titles) == ["A"]


async def test_to_sql_returns_a_string_without_running(db):
    Post = _post_model()
    sql = Post.where(Post.votes > 100).latest().to_sql()
    assert isinstance(sql, str)
    assert "posts" in sql.lower()


async def test_from_statement_wraps_a_raw_select(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=5)
    await Post.create(title="B", votes=1)
    stmt = select(Post).where(Post.votes > 2)
    rows = await Post.from_statement(stmt).get()
    assert [p.title for p in rows] == ["A"]


async def test_scope_can_start_a_query(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=0)
    rows = await Post.published().get()
    assert [p.title for p in rows] == ["A"]


async def test_scope_can_be_chained_onto_a_query(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=5)
    await Post.create(title="C", votes=0)
    rows = await Post.where(Post.title != "A").published().get()
    assert [p.title for p in rows] == ["B"]


async def test_scope_with_extra_argument(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        type_: Mapped[str] = mapped_column("type", String(50), default="news")

        @scope
        def of_type(cls, query: Builder, type_: str) -> Builder:  # noqa: N805
            return query.where(cls.type_ == type_)

    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", type_="news")
    await Post.create(title="B", type_="blog")
    rows = await Post.of_type("news").get()
    assert [p.title for p in rows] == ["A"]
