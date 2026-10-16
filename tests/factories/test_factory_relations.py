"""`for_<relation>`/`has_<relation>` and model <-> factory lookup by convention (T-36), against
the `tests/fixtures/factories_app` fixture (`User`/`Post`, `UserFactory`/`PostFactory`)."""

from __future__ import annotations

from aso.database import Factory, Model
from aso.database.factory import factory_for


async def test_for_relation_sets_the_foreign_key(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    import database.factories.post_factory as post_factory_module
    import database.factories.user_factory as user_factory_module

    user = await user_factory_module.UserFactory.new().create()
    post = await post_factory_module.PostFactory.new().for_user(user).create()
    assert post.user_id == user.id


async def test_has_relation_creates_children_with_the_foreign_key_set(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    import database.factories.user_factory as user_factory_module

    author = await user_factory_module.UserFactory.new().has_posts(3).create()
    posts = await Post.query().where(Post.user_id == author.id).get()
    assert len(posts) == 3


async def test_has_relation_accepts_a_configured_factory(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    import database.factories.post_factory as post_factory_module
    import database.factories.user_factory as user_factory_module

    configured = post_factory_module.PostFactory.new().count(2).state({"title": "Configured"})
    author = await user_factory_module.UserFactory.new().has_posts(configured).create()
    posts = await Post.query().where(Post.user_id == author.id).get()
    assert len(posts) == 2
    assert all(p.title == "Configured" for p in posts)


async def test_factory_for_resolves_by_convention(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    user_factory_cls = factory_for(User)
    assert user_factory_cls.__name__ == "UserFactory"
    assert issubclass(user_factory_cls, Factory)


async def test_user_factory_default_state_is_verified_and_hashes_the_password(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    import database.factories.user_factory as user_factory_module

    user = await user_factory_module.UserFactory.new().create()
    assert user.email_verified_at is not None
    assert user.password != "password"  # the Hashed column type hashed it on save


async def test_user_factory_unverified_state(db, factories_app):
    User, Post = factories_app
    await db.run_sync(Model.metadata.create_all)

    import database.factories.user_factory as user_factory_module

    user = await user_factory_module.UserFactory.new().unverified().create()
    assert user.email_verified_at is None
