"""T-33 Relationships: has_many/has_one/belongs_to/belongs_to_many, eager/lazy loading."""

from __future__ import annotations

import pytest
from sqlalchemy import ForeignKey, String

from aso.database import (
    LazyLoadingViolation,
    Mapped,
    Model,
    belongs_to,
    belongs_to_many,
    has_many,
    has_one,
    mapped_column,
)


def _blog_models():
    class User(Model):
        name: Mapped[str] = mapped_column(String(50))
        posts: Mapped[list[Post]] = has_many("Post")
        phone: Mapped[Phone | None] = has_one("Phone")

    class Phone(Model):
        number: Mapped[str] = mapped_column(String(50))
        user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
        user: Mapped[User] = belongs_to("User")

    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))
        user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
        user: Mapped[User] = belongs_to("User")
        tags: Mapped[list[Tag]] = belongs_to_many("Tag")
        comments: Mapped[list[Comment]] = has_many("Comment")

    class Tag(Model):
        name: Mapped[str] = mapped_column(String(50))
        posts: Mapped[list[Post]] = belongs_to_many("Post")

    class Comment(Model):
        body: Mapped[str] = mapped_column(String(50))
        post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
        post: Mapped[Post] = belongs_to("Post")

    return User, Phone, Post, Tag, Comment


# ---------------------------------------------------------------- default keys / pairing


async def test_has_many_belongs_to_default_foreign_key(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    loaded = await Post.with_("user").find(post.id)
    assert loaded.user.name == "Ada"


async def test_setting_belongs_to_updates_the_paired_has_many_when_loaded(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.with_("posts").find((await User.create(name="Ada")).id)
    post = Post(title="Hello")
    post.user = user  # back_populates pairing: should also land in user.posts
    assert post in user.posts


async def test_has_one_default_foreign_key(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    await Phone.create(number="555", user_id=user.id)
    loaded = await User.with_("phone").find(user.id)
    assert loaded.phone.number == "555"


async def test_belongs_to_many_default_pivot_and_keys(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    assert "post_tag" in Model.metadata.tables
    pivot = Model.metadata.tables["post_tag"]
    assert {c.name for c in pivot.columns} == {"post_id", "tag_id"}


async def test_belongs_to_many_is_paired_both_ways(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    tag = await Tag.create(name="python")
    await post.relation("tags").attach([tag.id])
    loaded_tag = await Tag.with_("posts").find(tag.id)
    assert [p.title for p in loaded_tag.posts] == ["Hello"]


# ---------------------------------------------------------------- lazy load guard


async def test_unloaded_relation_raises_lazy_loading_violation(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    fresh = await Post.find(post.id)
    with pytest.raises(LazyLoadingViolation) as exc_info:
        _ = fresh.user
    message = str(exc_info.value)
    assert "Post" in message and "user" in message
    assert 'with_("user")' in message or 'with_(' in message


async def test_relation_loaded_checks_without_raising(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    fresh = await Post.find(post.id)
    assert fresh.relation_loaded("user") is False
    loaded = await Post.with_("user").find(post.id)
    assert loaded.relation_loaded("user") is True


# ---------------------------------------------------------------- with_() nested, load(), load_missing()


async def test_with_nested_dotted_path(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    await Comment.create(body="Nice", post_id=post.id)
    loaded = await Comment.with_("post.user").find((await Comment.query().first()).id)
    assert loaded.post.user.name == "Ada"


async def test_with_dict_constraint_filters_the_relation(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    await Comment.create(body="Approved", post_id=post.id)
    await Comment.create(body="Spam", post_id=post.id)

    loaded = await Post.with_(
        {"comments": lambda q: q.where(Comment.body == "Approved"), "user": None}
    ).find(post.id)
    assert [c.body for c in loaded.comments] == ["Approved"]
    assert loaded.user.name == "Ada"


async def test_with_constraint_ordering_raises_a_clear_error(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    with pytest.raises(ValueError, match="order_by"):
        Post.with_({"comments": lambda q: q.order_by(Comment.body)})


async def test_load_direct_relation(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    fresh = await Post.find(post.id)
    await fresh.load("user")
    assert fresh.user.name == "Ada"


async def test_load_missing_only_loads_what_is_missing(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    loaded = await Post.with_("user").find(post.id)
    await loaded.load_missing("user")  # already loaded: must not raise
    assert loaded.user.name == "Ada"
    fresh = await Post.find(post.id)
    await fresh.load_missing("user")
    assert fresh.user.name == "Ada"


async def test_load_returns_self_for_inline_use(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    fresh = await Post.find(post.id)
    result = await fresh.load("user")
    assert result is fresh


# ---------------------------------------------------------------- relation(name) querying + writes


async def test_relation_builder_queries_scoped_to_owner(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    a = await User.create(name="A")
    b = await User.create(name="B")
    await Post.create(title="A1", user_id=a.id)
    await Post.create(title="A2", user_id=a.id)
    await Post.create(title="B1", user_id=b.id)
    rows = await a.relation("posts").get()
    assert {p.title for p in rows} == {"A1", "A2"}
    assert await a.relation("posts").count() == 2


async def test_relation_create_sets_the_foreign_key(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    comment = await post.relation("comments").create(body="Nice post!")
    assert comment.post_id == post.id


async def test_relation_create_many(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    created = await post.relation("comments").create_many([{"body": "A"}, {"body": "B"}])
    assert {c.body for c in created} == {"A", "B"}
    assert await post.relation("comments").count() == 2


async def test_belongs_to_many_attach_detach_sync_toggle(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    t1 = await Tag.create(name="python")
    t2 = await Tag.create(name="web")
    t3 = await Tag.create(name="fastapi")

    await post.relation("tags").attach([t1.id, t2.id])
    assert await post.relation("tags").count() == 2

    await post.relation("tags").detach(t2.id)
    assert {t.name for t in await post.relation("tags").get()} == {"python"}

    result = await post.relation("tags").sync([t2.id, t3.id])
    assert sorted(result["attached"]) == sorted([t2.id, t3.id])
    assert result["detached"] == [t1.id]
    assert {t.name for t in await post.relation("tags").get()} == {"web", "fastapi"}

    toggled = await post.relation("tags").toggle([t1.id, t2.id])
    assert toggled["attached"] == [t1.id]
    assert toggled["detached"] == [t2.id]
    assert {t.name for t in await post.relation("tags").get()} == {"python", "fastapi"}


async def test_attach_does_not_duplicate_existing_pivot_rows(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    tag = await Tag.create(name="python")
    await post.relation("tags").attach([tag.id])
    await post.relation("tags").attach([tag.id])  # must not raise or duplicate
    assert await post.relation("tags").count() == 1


async def test_detach_with_no_ids_removes_all(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    t1 = await Tag.create(name="a")
    t2 = await Tag.create(name="b")
    await post.relation("tags").attach([t1.id, t2.id])
    await post.relation("tags").detach()
    assert await post.relation("tags").count() == 0


# ---------------------------------------------------------------- with_count, where_has, doesnt_have


async def test_with_count(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    await Comment.create(body="A", post_id=post.id)
    await Comment.create(body="B", post_id=post.id)
    await Post.create(title="Empty", user_id=user.id)

    rows = await Post.with_count("comments").order_by(Post.title).get()
    counts = {p.title: p.comments_count for p in rows}
    assert counts == {"Empty": 0, "Hello": 2}


async def test_with_count_with_constraint(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    await Comment.create(body="Approved", post_id=post.id)
    await Comment.create(body="Spam", post_id=post.id)

    rows = await Post.with_count({"comments": lambda q: q.where(Comment.body == "Approved")}).get()
    assert rows[0].comments_count == 1


async def test_where_has_filters_by_relation_existence(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    with_comment = await Post.create(title="WithComment", user_id=user.id)
    await Post.create(title="NoComment", user_id=user.id)
    await Comment.create(body="Nice", post_id=with_comment.id)

    rows = await Post.where_has("comments").get()
    assert [p.title for p in rows] == ["WithComment"]


async def test_where_has_with_constraint(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    post = await Post.create(title="Hello", user_id=user.id)
    await Comment.create(body="Approved", post_id=post.id)

    rows = await Post.where_has("comments", lambda q: q.where(Comment.body == "Approved")).get()
    assert [p.title for p in rows] == ["Hello"]
    rows2 = await Post.where_has("comments", lambda q: q.where(Comment.body == "Nope")).get()
    assert rows2 == []


async def test_doesnt_have(db):
    User, Phone, Post, Tag, Comment = _blog_models()
    await db.run_sync(Model.metadata.create_all)
    user = await User.create(name="Ada")
    with_comment = await Post.create(title="WithComment", user_id=user.id)
    no_comment = await Post.create(title="NoComment", user_id=user.id)
    await Comment.create(body="Nice", post_id=with_comment.id)

    rows = await Post.doesnt_have("comments").get()
    assert [p.title for p in rows] == [no_comment.title]


# ---------------------------------------------------------------- __touches__


async def test_touches_updates_parent_updated_at(db):
    # A standalone pair, not `_blog_models()`'s Post/Comment: that fixture's `Comment` has no
    # `__touches__`, and defining a second class also named `Comment` would clash with its
    # already-registered "comments" table in `Model.metadata`.
    class Article(Model):
        title: Mapped[str] = mapped_column(String(50))

    class Remark(Model):
        __touches__ = ["article"]
        body: Mapped[str] = mapped_column(String(50))
        article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
        article: Mapped[Article] = belongs_to("Article")

    await db.run_sync(Model.metadata.create_all)
    article = await Article.create(title="Hello")
    original_updated_at = article.updated_at

    loaded_article = await Article.find(article.id)
    remark = Remark(body="Nice")
    remark.article = loaded_article  # loads the relation on the remark side
    await remark.save()

    assert loaded_article.updated_at >= original_updated_at
