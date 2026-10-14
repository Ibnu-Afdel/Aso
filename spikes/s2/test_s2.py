"""S-2 spike tests. Run with DB_URL unset (SQLite) and DB_URL=postgresql+asyncpg://... ."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import ForeignKey, String, exc as sa_exc, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column, selectinload
from sqlalchemy.pool import StaticPool

from db import DB, LazyLoadingViolation, Model, _test_binding, belongs_to, configure, has_many


class User(Model):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(100), unique=True)
    posts: Mapped[list["Post"]] = has_many("Post", back_populates="author")


class Post(Model):
    __tablename__ = "posts"
    title: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped[User] = belongs_to("User", back_populates="posts")


URL = os.environ.get("DB_URL", "sqlite+aiosqlite://")


@pytest.fixture(scope="session")
async def engine():
    kw: dict[str, Any] = {}
    if URL.startswith("sqlite"):
        kw = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    eng = create_async_engine(URL, **kw)
    async with eng.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    configure(eng)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine):
    """T-57 test binding: one connection + outer transaction; each scope gets its own session."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        token = _test_binding.set(conn)
        try:
            async with DB.scope():
                yield
        finally:
            _test_binding.reset(token)
            await trans.rollback()


class DatabaseScope:
    """Pure ASGI middleware: a fresh scope per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async with DB.scope(fresh=True):
            await self.app(scope, receive, send)


def make_app() -> FastAPI:
    app = FastAPI()

    @app.post("/users")
    async def create_user(email: str):
        user = await User.create(email=email)
        await Post.create(title="hello", user_id=user.id)
        return {"id": user.id, "session_id": id(DB.session())}

    @app.get("/posts/{id}/author")
    async def lazy(id: int):
        post = await Post.find(id)
        try:
            return {"author": post.author.email}
        except LazyLoadingViolation as e:
            return {"error": str(e)}

    @app.get("/session-id")
    async def sid():
        return {"session_id": id(DB.session())}

    app.add_middleware(DatabaseScope)
    return app


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_route_gets_its_own_session_and_writes_are_visible_to_test(db):
    test_session = DB.session()
    async with client(make_app()) as c:
        r = await c.post("/users", params={"email": "a@x.io"})
        assert r.status_code == 200, r.text
        assert r.json()["session_id"] != id(test_session)
        r2 = await c.get("/session-id")
        assert r2.status_code == 200
    users = await User.all()
    assert [u.email for u in users] == ["a@x.io"]


async def test_previous_test_was_rolled_back(db):
    assert await User.all() == []


async def test_lazy_load_is_blocked_with_clear_error(db):
    async with client(make_app()) as c:
        await c.post("/users", params={"email": "b@x.io"})
        post = (await Post.all())[0]
        r = await c.get(f"/posts/{post.id}/author")
    assert "Attempted to lazy load [author] on model [Post]" in r.json()["error"]
    assert 'Post.with_("author")' in r.json()["error"]


async def test_job_runs_in_its_own_scope(db):
    request_session = DB.session()

    async def job():
        async with DB.scope(fresh=True):
            assert DB.session() is not request_session
            u = await User.create(email="job@x.io")
            return u.id

    uid = await asyncio.create_task(job())
    assert (await User.find(uid)).email == "job@x.io"


async def test_write_after_read(db):
    await User.create(email="r@x.io")
    users = await User.all()
    u = await User.create(email="w@x.io")
    assert u.id and len(users) == 1
    async with DB.transaction():
        await User.create(email="t@x.io")
    assert len(await User.all()) == 3


async def test_failed_write_keeps_logged_in_user_readable(db):
    me = await User.create(email="me@x.io")
    other = await User.create(email="dupe@x.io")
    with pytest.raises(sa_exc.IntegrityError):
        await User.create(email="dupe@x.io")
    assert me.email == "me@x.io" and other.email == "dupe@x.io"
    assert len(await User.all()) == 2


async def test_failed_transaction_then_read_user(db):
    me = await User.create(email="me2@x.io")
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            await User.create(email="gone@x.io")
            raise RuntimeError("boom")
    assert me.email == "me2@x.io"
    assert [u.email for u in await User.all()] == ["me2@x.io"]


async def test_nested_rollback(db):
    async with DB.transaction():
        await User.create(email="outer@x.io")
        try:
            async with DB.transaction():
                await User.create(email="inner@x.io")
                raise ValueError
        except ValueError:
            pass
        await User.create(email="outer2@x.io")
    assert sorted(u.email for u in await User.all()) == ["outer2@x.io", "outer@x.io"]


async def test_changed_model_is_expired_after_rollback(db):
    u = await User.create(email="before@x.io")
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            u.email = "after@x.io"
            await u.save()
            raise RuntimeError
    await u.refresh()
    assert u.email == "before@x.io"


async def test_after_commit_runs_only_on_commit(db):
    ran: list[str] = []
    async with DB.transaction():
        await User.create(email="ac@x.io")
        DB.after_commit(lambda: ran.append("yes"))
        assert ran == []
    assert ran == ["yes"]
    with pytest.raises(RuntimeError):
        async with DB.transaction():
            DB.after_commit(lambda: ran.append("no"))
            raise RuntimeError
    assert ran == ["yes"]


async def test_eager_load_works(db):
    u = await User.create(email="e@x.io")
    await Post.create(title="p", user_id=u.id)
    async with DB.scope(fresh=True):
        post = (await DB.session().scalars(select(Post).options(selectinload(Post.author)))).one()
        assert post.author.email == "e@x.io"
