"""T-32 Querying: increment/decrement, chunk, lazy."""

from __future__ import annotations

from sqlalchemy import String

from aso.database import Mapped, Model, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        votes: Mapped[int] = mapped_column(default=0)

    return Post


async def test_increment_and_decrement(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="A", votes=10)
    await Post.where(Post.id == post.id).increment(Post.votes)
    await post.refresh()
    assert post.votes == 11
    await Post.where(Post.id == post.id).decrement(Post.votes, by=5)
    await post.refresh()
    assert post.votes == 6


async def test_increment_with_extra_columns(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="A", votes=10)
    await Post.where(Post.id == post.id).increment(Post.votes, by=2, title="B")
    await post.refresh()
    assert post.votes == 12
    assert post.title == "B"


async def test_chunk_iterates_in_pages(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    for i in range(7):
        await Post.create(title=str(i), votes=i)
    seen = []
    async for page in Post.order_by(Post.votes).chunk(3):
        seen.append([p.title for p in page])
    assert seen == [["0", "1", "2"], ["3", "4", "5"], ["6"]]


async def test_chunk_on_empty_table_yields_nothing(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    pages = [p async for p in Post.chunk(10)]
    assert pages == []


async def test_lazy_iterates_one_model_at_a_time(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    for i in range(5):
        await Post.create(title=str(i), votes=i)
    titles = [p.title async for p in Post.order_by(Post.votes).lazy(2)]
    assert titles == ["0", "1", "2", "3", "4"]
