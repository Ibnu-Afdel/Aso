"""T-31 Models: table naming, timestamps, mass assignment, dirty tracking, serialisation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import String

from aso.config import set_config
from aso.database import Mapped, MassAssignmentError, Model, mapped_column

# ---------------------------------------------------------------- table naming (T-31)


def test_table_name_is_snake_case_plural_of_class_name():
    class BlogPost(Model):
        title: Mapped[str] = mapped_column(String(50), default="x")

    assert BlogPost.__tablename__ == "blog_posts"


def test_table_name_handles_irregular_plurals():
    class Category(Model):
        name: Mapped[str] = mapped_column(String(50), default="x")

    class Person(Model):
        name: Mapped[str] = mapped_column(String(50), default="x")

    assert Category.__tablename__ == "categories"
    assert Person.__tablename__ == "people"


def test_table_name_override():
    class Post(Model):
        __tablename__ = "articles"
        title: Mapped[str] = mapped_column(String(50), default="x")

    assert Post.__tablename__ == "articles"


# ---------------------------------------------------------------- timestamps (T-30, T-31)


async def test_timestamps_are_aware_utc_and_set_on_insert(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    before = datetime.now(UTC)
    post = await Post.create(title="Hello")
    assert post.created_at.tzinfo is not None
    assert post.created_at.utcoffset().total_seconds() == 0
    assert post.created_at >= before - timedelta_tolerance()
    assert post.updated_at == post.created_at


def timedelta_tolerance():
    from datetime import timedelta

    return timedelta(seconds=5)


async def test_updated_at_changes_on_save_but_not_created_at(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Hello")
    created = post.created_at
    post.title = "Hello again"
    await post.save()
    assert post.created_at == created
    assert post.updated_at >= created


async def test_timestamps_can_be_disabled():
    class Post(Model):
        __timestamps__ = False
        title: Mapped[str] = mapped_column(String(50))

    assert not hasattr(Post, "created_at")
    assert not hasattr(Post, "updated_at")


async def test_naive_datetime_is_rejected_by_utc_datetime_column(db):
    class Event(Model):
        __tablename__ = "evts"
        happened_at: Mapped[datetime]

    from sqlalchemy.exc import StatementError

    await db.run_sync(Model.metadata.create_all)
    with pytest.raises((ValueError, StatementError)) as exc_info:
        await Event.create(happened_at=datetime(2026, 1, 1))  # noqa: DTZ001 - testing the guard
    assert "naive datetime" in str(exc_info.value)


async def test_aware_datetime_round_trips_as_utc_even_on_sqlite(db):
    from datetime import timedelta

    class Event(Model):
        __tablename__ = "evts2"
        happened_at: Mapped[datetime]

    await db.run_sync(Model.metadata.create_all)
    tz_plus2 = UTC
    local = datetime(2026, 6, 1, 12, 0, tzinfo=tz_plus2) + timedelta(hours=2)
    event = await Event.create(happened_at=local)
    fresh = await Event.find(event.id)
    assert fresh.happened_at.tzinfo is not None
    assert fresh.happened_at == local.astimezone(UTC)


# ---------------------------------------------------------------- mass assignment (T-31)


async def test_fillable_allows_listed_keys_only(db):
    set_config("app.environment", "testing")
    try:

        class User(Model):
            __fillable__ = ["name"]
            name: Mapped[str] = mapped_column(String(50))
            is_admin: Mapped[bool] = mapped_column(default=False)

        await db.run_sync(Model.metadata.create_all)
        with pytest.raises(MassAssignmentError):
            await User.create(name="Ada", is_admin=True)
        user = await User.create(name="Ada")
        assert user.is_admin is False
    finally:
        set_config("app.environment", "testing")


async def test_guarded_blocks_listed_keys_only(db):
    set_config("app.environment", "testing")

    class User(Model):
        __guarded__ = ["is_admin"]
        name: Mapped[str] = mapped_column(String(50))
        is_admin: Mapped[bool] = mapped_column(default=False)

    await db.run_sync(Model.metadata.create_all)
    with pytest.raises(MassAssignmentError):
        await User.create(name="Ada", is_admin=True)
    user = await User.create(name="Ada")
    assert user.name == "Ada"


async def test_mass_assignment_in_production_drops_the_key_instead_of_raising(db):
    set_config("app.environment", "production")
    try:

        class User(Model):
            __fillable__ = ["name"]
            name: Mapped[str] = mapped_column(String(50))
            is_admin: Mapped[bool] = mapped_column(default=False)

        await db.run_sync(Model.metadata.create_all)
        user = await User.create(name="Ada", is_admin=True)
        assert user.is_admin is False
    finally:
        set_config("app.environment", "testing")


async def test_setattr_directly_is_never_restricted(db):
    set_config("app.environment", "testing")

    class User(Model):
        __fillable__ = ["name"]
        name: Mapped[str] = mapped_column(String(50))
        is_admin: Mapped[bool] = mapped_column(default=False)

    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    user.is_admin = True
    await user.save()
    assert user.is_admin is True


async def test_fill_unknown_key_raises_attribute_error(db):
    class User(Model):
        name: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    user = User(name="Ada")
    with pytest.raises(AttributeError):
        user.fill(nickname="Ace")


async def test_update_calls_fill_then_save(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Draft")
    await post.update(title="Final")
    assert post.title == "Final"
    assert (await Post.find(post.id)).title == "Final"


# ---------------------------------------------------------------- dirty tracking (T-31)


async def test_is_dirty_and_get_original_and_was_changed(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Old")
    assert post.is_dirty() is False
    post.title = "New"
    assert post.is_dirty() is True
    assert post.is_dirty("title") is True
    assert post.get_original("title") == "Old"
    await post.save()
    assert post.was_changed("title") is True
    assert post.was_changed() is True
    assert post.is_dirty() is False


async def test_save_with_nothing_dirty_is_a_no_op(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Old")
    updated_at = post.updated_at
    await post.save()
    assert post.updated_at == updated_at


# ---------------------------------------------------------------- refreshing (T-31)


async def test_refresh_reloads_columns(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Old")
    await Post.where(Post.id == post.id).update(title="Changed elsewhere")
    await post.refresh()
    assert post.title == "Changed elsewhere"


async def test_fresh_is_an_alias_for_refresh_and_returns_self(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    post = await Post.create(title="Old")
    await Post.where(Post.id == post.id).update(title="Changed")
    same = await post.fresh()
    assert same is post
    assert same.title == "Changed"


# ---------------------------------------------------------------- comparing (T-31)


async def test_is_and_is_not_compare_table_and_primary_key(db):
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    await db.run_sync(Model.metadata.create_all)
    a = await Post.create(title="A")
    b = await Post.create(title="B")
    same = await Post.find(a.id)
    assert a.is_(same) is True
    assert a.is_not(b) is True
    assert a.is_(b) is False
    assert a.is_("not a model") is False


# ---------------------------------------------------------------- serialisation (T-31)


async def test_to_dict_excludes_hidden_and_includes_appends(db):
    class User(Model):
        __hidden__ = ["password"]
        __appends__ = ["shout"]
        name: Mapped[str] = mapped_column(String(50))
        password: Mapped[str] = mapped_column(String(50))

        @property
        def shout(self) -> str:
            return self.name.upper()

    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada", password="secret")
    data = user.to_dict()
    assert "password" not in data
    assert data["shout"] == "ADA"
    assert data["name"] == "Ada"


async def test_to_dict_never_triggers_a_relation_load(db):
    from sqlalchemy import ForeignKey

    from aso.database import belongs_to, has_many

    class User(Model):
        name: Mapped[str] = mapped_column(String(50))
        posts: Mapped[list[Post]] = has_many("Post")

    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
        user: Mapped[User] = belongs_to("User")

    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hi", user_id=user.id)
    fresh_post = await Post.find(post.id)
    data = fresh_post.to_dict()  # must not raise LazyLoadingViolation
    assert "user" not in data


async def test_to_dict_includes_already_loaded_relations(db):
    from sqlalchemy import ForeignKey

    from aso.database import belongs_to, has_many

    class User(Model):
        name: Mapped[str] = mapped_column(String(50))
        posts: Mapped[list[Post]] = has_many("Post")

    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
        user: Mapped[User] = belongs_to("User")

    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    await Post.create(title="Hi", user_id=user.id)
    loaded = await Post.with_("user").first()
    data = loaded.to_dict()
    assert data["user"]["name"] == "Ada"


async def test_only_returns_requested_keys():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50), default="x")
        body: Mapped[str] = mapped_column(String(50), default="y")

    post = Post(title="Hi", body="World")
    assert post.only("title") == {"title": "Hi"}


async def test_make_hidden_and_make_visible(db):
    class User(Model):
        __hidden__ = ["password"]
        name: Mapped[str] = mapped_column(String(50))
        password: Mapped[str] = mapped_column(String(50))
        notes: Mapped[str] = mapped_column(String(50), default="")

    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada", password="secret")
    data = user.make_hidden("name").to_dict()
    assert "name" not in data
    assert "password" not in data
    data2 = user.make_visible("password").to_dict()
    assert "password" in data2
