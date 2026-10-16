"""T-32 Querying: where forms, grouping, when/unless."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import String

from aso.database import Mapped, Model, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        votes: Mapped[int] = mapped_column(default=0)
        featured: Mapped[bool] = mapped_column(default=False)

    return Post


async def test_where_with_column_expression(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=10)
    await Post.create(title="B", votes=200)
    rows = await Post.where(Post.votes > 100).get()
    assert [p.title for p in rows] == ["B"]


async def test_where_multiple_args_is_and(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=200, featured=True)
    await Post.create(title="B", votes=200, featured=False)
    rows = await Post.where(Post.votes >= 100, Post.featured == True).get()  # noqa: E712
    assert [p.title for p in rows] == ["A"]


async def test_chained_where_is_and(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=200, featured=True)
    await Post.create(title="B", votes=200, featured=False)
    rows = await Post.where(Post.votes >= 100).where(Post.featured == True).get()  # noqa: E712
    assert [p.title for p in rows] == ["A"]


async def test_where_keyword_equality_shortcut(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="draft", votes=1)
    await Post.create(title="published", votes=1)
    rows = await Post.where(title="published").get()
    assert [p.title for p in rows] == ["published"]


async def test_or_where(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=200, featured=False)
    await Post.create(title="B", votes=1, featured=True)
    await Post.create(title="C", votes=1, featured=False)
    rows = await Post.where(Post.votes > 100).or_where(Post.featured == True).get()  # noqa: E712
    assert {p.title for p in rows} == {"A", "B"}


async def test_where_in_and_not_in(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A")
    b = await Post.create(title="B")
    await Post.create(title="C")
    rows = await Post.where_in(Post.id, [a.id, b.id]).get()
    assert {p.title for p in rows} == {"A", "B"}
    rows2 = await Post.where_not_in(Post.id, [a.id, b.id]).get()
    assert [p.title for p in rows2] == ["C"]


async def test_where_null_and_not_null(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        published_at: Mapped[str | None] = mapped_column(String(50), default=None)

    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="Draft")
    await Post.create(title="Live", published_at="2026-01-01")
    rows = await Post.where_null(Post.published_at).get()
    assert [p.title for p in rows] == ["Draft"]
    rows2 = await Post.where_not_null(Post.published_at).get()
    assert [p.title for p in rows2] == ["Live"]


async def test_where_between(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=5)
    await Post.create(title="B", votes=50)
    await Post.create(title="C", votes=500)
    rows = await Post.where_between(Post.votes, 1, 100).get()
    assert {p.title for p in rows} == {"A", "B"}


async def test_where_date(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        published_at: Mapped[datetime]

    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", published_at=datetime(2026, 10, 1, 8, tzinfo=UTC))
    await Post.create(title="B", published_at=datetime(2026, 10, 2, 8, tzinfo=UTC))
    rows = await Post.where_date(Post.published_at, date(2026, 10, 1)).get()
    assert [p.title for p in rows] == ["A"]


async def test_grouping_conditions_with_a_lambda(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=200, featured=False)  # matches group (votes>100)
    await Post.create(title="B", votes=1, featured=True)  # matches group (featured)
    await Post.create(title="C", votes=1, featured=False)  # no match

    rows = await Post.where(
        lambda q: q.where(Post.votes > 100).or_where(Post.featured == True)  # noqa: E712
    ).get()
    assert {p.title for p in rows} == {"A", "B"}


async def test_when_runs_callback_only_if_value_truthy(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    search = "A"
    rows = await Post.query().when(search, lambda q: q.where(Post.title == search)).get()
    assert [p.title for p in rows] == ["A"]
    rows2 = await Post.query().when(None, lambda q: q.where(Post.title == search)).get()
    assert len(rows2) == 2


async def test_when_passes_value_as_second_argument(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    rows = await Post.query().when("A", lambda q, v: q.where(title=v)).get()
    assert [p.title for p in rows] == ["A"]


async def test_unless_is_the_inverse_of_when(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    rows = await Post.query().unless(False, lambda q: q.where(Post.title == "A")).get()
    assert [p.title for p in rows] == ["A"]
    rows2 = await Post.query().unless(True, lambda q: q.where(Post.title == "A")).get()
    assert len(rows2) == 2


async def test_base_query_is_not_mutated_by_further_chaining(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=2)
    base = Post.where(Post.votes > 0)
    narrowed = base.where(Post.title == "A")
    assert await base.get() != await narrowed.get() or len(await base.get()) == 2
    assert len(await base.get()) == 2
    assert len(await narrowed.get()) == 1
