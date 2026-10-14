"""T-31 Models: `SoftDeletes` mixin."""

from __future__ import annotations

from sqlalchemy import String

from fastogram.database import Mapped, Model, SoftDeletes, mapped_column


def _post_model():
    class Post(SoftDeletes, Model):
        title: Mapped[str] = mapped_column(String(50))

    return Post


async def test_delete_sets_deleted_at_instead_of_removing_the_row(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    assert post.deleted_at is not None
    assert post.trashed() is True


async def test_normal_queries_hide_soft_deleted_rows(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    assert await Post.find(post.id) is None
    assert await Post.all() == []
    assert await Post.count() == 0


async def test_with_trashed_includes_soft_deleted_rows(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    await Post.create(title="Kept")
    rows = await Post.with_trashed().get()
    assert {p.title for p in rows} == {"Gone", "Kept"}


async def test_only_trashed_returns_just_soft_deleted_rows(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    await Post.create(title="Kept")
    rows = await Post.only_trashed().get()
    assert [p.title for p in rows] == ["Gone"]


async def test_restore_clears_deleted_at(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    await post.restore()
    assert post.deleted_at is None
    assert post.trashed() is False
    assert await Post.find(post.id) is not None


async def test_force_delete_removes_the_row(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.force_delete()
    rows = await Post.with_trashed().get()
    assert rows == []


async def test_bulk_delete_on_soft_deleting_model_is_an_update(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    affected = await Post.where(Post.title == "A").delete()
    assert affected == 1
    assert await Post.count() == 1
    rows = await Post.with_trashed().get()
    assert len(rows) == 2
