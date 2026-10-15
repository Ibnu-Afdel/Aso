"""`Factory` core behaviour (T-36): `definition()`, `state()`, `count()`, `make()`/`create()`,
bypassing `__fillable__`, and rejecting unknown attributes. Models are declared inside each test
function (see `tests/database/conftest.py`'s docstring on why)."""

from __future__ import annotations

import pytest
from sqlalchemy import String, Text

from fastogram.database import Factory, Mapped, Model, mapped_column


def _make_post_model():
    class Post(Model):
        __fillable__ = ["title"]

        title: Mapped[str] = mapped_column(String(255))
        body: Mapped[str] = mapped_column(Text)

    return Post


async def test_create_persists_and_returns_a_single_model(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Hello", "body": "World"}

    post = await PostFactory.new().create()
    assert post.id is not None
    assert post.title == "Hello"
    found = await Post.find(post.id)
    assert found is not None
    assert found.title == "Hello"


async def test_make_does_not_persist(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Hello", "body": "World"}

    post = PostFactory.new().make()
    assert post.id is None
    assert await Post.count() == 0


async def test_count_returns_a_list_of_the_requested_size(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": self.faker.sentence(), "body": self.faker.paragraph()}

    posts = await PostFactory.new().count(5).create()
    assert len(posts) == 5
    assert await Post.count() == 5

    made = PostFactory.new().count(3).make()
    assert len(made) == 3
    assert all(p.id is None for p in made)


async def test_state_overrides_the_definition(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Default", "body": "x"}

        def titled_hello(self):
            return self.state({"title": "Hello"})

    post = await PostFactory.new().titled_hello().create()
    assert post.title == "Hello"


async def test_overrides_passed_to_create_win_over_state(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Default", "body": "x"}

    post = await PostFactory.new().state({"title": "State"}).create(title="Override")
    assert post.title == "Override"


async def test_factory_bypasses_fillable(db):
    """`__fillable__ = ["title"]` on `Post`, but the factory still sets `body`."""
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Hello", "body": "Not fillable but still set"}

    post = await PostFactory.new().create()
    assert post.body == "Not fillable but still set"


async def test_unknown_attribute_name_raises_attribute_error(db):
    from fastogram.database import Model

    Post = _make_post_model()
    await db.run_sync(Model.metadata.create_all)

    class PostFactory(Factory):
        model = Post

        def definition(self) -> dict:
            return {"title": "Hello", "not_a_real_column": 1}

    with pytest.raises(AttributeError):
        PostFactory.new().make()


async def test_faker_locale_comes_from_config(db):
    from fastogram.config import set_config

    Post = _make_post_model()
    from fastogram.database import Model

    await db.run_sync(Model.metadata.create_all)

    set_config("app.faker_locale", "ja_JP")
    try:

        class PostFactory(Factory):
            model = Post

            def definition(self) -> dict:
                return {"title": "x", "body": "y"}

        f = PostFactory.new()
        assert "ja_JP" in f.faker.locales
    finally:
        set_config("app.faker_locale", None)
