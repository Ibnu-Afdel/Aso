"""T-32 Querying: terminal methods (get/first/sole/value/pluck/aggregates/exists)."""

from __future__ import annotations

import pytest
from sqlalchemy import String

from fastogram.database import Mapped, Model, ModelNotFound, MultipleRecordsFound, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        votes: Mapped[int] = mapped_column(default=0)

    return Post


async def test_get_returns_a_list(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    rows = await Post.query().get()
    assert isinstance(rows, list)
    assert len(rows) == 2


async def test_first_returns_none_when_empty(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    assert await Post.query().first() is None


async def test_first_or_fail_raises(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    with pytest.raises(ModelNotFound):
        await Post.query().first_or_fail()


async def test_sole_raises_when_zero_or_many(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    with pytest.raises(ModelNotFound):
        await Post.query().sole()
    await Post.create(title="A")
    await Post.create(title="A")
    with pytest.raises(MultipleRecordsFound):
        await Post.where(Post.title == "A").sole()


async def test_sole_returns_the_single_match(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="Only")
    found = await Post.query().sole()
    assert found.title == "Only"


async def test_builder_find_respects_existing_constraints(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A", votes=1)
    b = await Post.create(title="B", votes=100)
    assert await Post.where(Post.votes > 50).find(a.id) is None
    assert (await Post.where(Post.votes > 50).find(b.id)).title == "B"


async def test_value_returns_first_rows_column(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=1)
    await Post.create(title="B", votes=2)
    assert await Post.order_by(Post.votes).value(Post.title) == "A"


async def test_pluck_without_key_returns_a_list(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    titles = await Post.order_by(Post.title).pluck(Post.title)
    assert titles == ["A", "B"]


async def test_pluck_with_key_returns_a_dict(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A")
    b = await Post.create(title="B")
    mapping = await Post.pluck(Post.title, Post.id)
    assert mapping == {a.id: "A", b.id: "B"}


async def test_count_exists_doesnt_exist(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    assert await Post.count() == 0
    assert await Post.exists() is False
    assert await Post.doesnt_exist() is True
    await Post.create(title="A")
    assert await Post.count() == 1
    assert await Post.exists() is True
    assert await Post.doesnt_exist() is False


async def test_sum_avg_min_max(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A", votes=10)
    await Post.create(title="B", votes=20)
    await Post.create(title="C", votes=30)
    assert await Post.sum(Post.votes) == 60
    assert await Post.avg(Post.votes) == 20
    assert await Post.min(Post.votes) == 10
    assert await Post.max(Post.votes) == 30


async def test_aggregates_on_empty_table_return_none_or_zero(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    assert await Post.sum(Post.votes) in (0, None)
    assert await Post.avg(Post.votes) is None
    assert await Post.max(Post.votes) is None
