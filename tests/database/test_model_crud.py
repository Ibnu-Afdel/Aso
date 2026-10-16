"""T-31 Models: retrieving, inserting, updating, deleting."""

from __future__ import annotations

import pytest
from sqlalchemy import String

from aso.database import Mapped, Model, ModelNotFound, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    return Post


async def test_create_persists_and_returns_the_instance(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Hello")
    assert post.id is not None
    assert (await Post.find(post.id)).title == "Hello"


async def test_save_on_a_new_instance_inserts(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = Post(title="Draft")
    await post.save()
    assert post.id is not None
    assert await Post.count() == 1


async def test_find_returns_none_when_missing(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    assert await Post.find(999) is None


async def test_find_or_fail_raises_model_not_found(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    with pytest.raises(ModelNotFound):
        await Post.find_or_fail(999)


async def test_find_many_returns_matching_subset(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A")
    b = await Post.create(title="B")
    await Post.create(title="C")
    found = await Post.find_many([a.id, b.id])
    assert {p.title for p in found} == {"A", "B"}


async def test_first_where(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    found = await Post.first_where(Post.title == "B")
    assert found.title == "B"
    assert await Post.first_where(Post.title == "nope") is None


async def test_all_and_count(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    assert len(await Post.all()) == 2
    assert await Post.count() == 2


async def test_first_or_create_returns_existing_without_inserting(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    existing = await Post.create(title="Hello")
    found = await Post.first_or_create({"title": "Hello"}, {"title": "Ignored"})
    assert found.id == existing.id
    assert await Post.count() == 1


async def test_first_or_create_creates_when_missing(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    created = await Post.first_or_create({"title": "New"})
    assert created.id is not None
    assert await Post.count() == 1


async def test_update_or_create_updates_existing(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    existing = await Post.create(title="Old")
    updated = await Post.update_or_create({"title": "Old"}, {"title": "New"})
    assert updated.id == existing.id
    assert updated.title == "New"
    assert await Post.count() == 1


async def test_update_or_create_creates_when_missing(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    created = await Post.update_or_create({"title": "New"}, {"title": "New v2"})
    assert created.title == "New v2"
    assert await Post.count() == 1


async def test_bulk_mass_update_one_query(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    affected = await Post.where(Post.title.in_(["A", "B"])).update(title="Z")
    assert affected == 2
    assert {p.title for p in await Post.all()} == {"Z"}


async def test_delete_instance(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Gone")
    await post.delete()
    assert await Post.find(post.id) is None


async def test_destroy_many(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A")
    b = await Post.create(title="B")
    c = await Post.create(title="C")
    count = await Post.destroy([a.id, b.id, 999])
    assert count == 2
    assert await Post.count() == 1
    assert (await Post.all())[0].id == c.id


async def test_bulk_delete(db):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await Post.create(title="A")
    await Post.create(title="B")
    affected = await Post.where(Post.title == "A").delete()
    assert affected == 1
    assert await Post.count() == 1
