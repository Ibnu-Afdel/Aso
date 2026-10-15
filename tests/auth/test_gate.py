"""Unit tests for `Gate` (T-39, D-030): gates, policy convention lookup, `before()`, the guest
rule, and `Authenticatable.can()/cannot()`."""

from __future__ import annotations

import sys
import types

import pytest

from fastogram.auth import Gate
from fastogram.auth.gate import AuthorizationException


class _User:
    def __init__(self, id: int, is_admin: bool = False) -> None:
        self.id = id
        self.is_admin = is_admin


class _Post:
    def __init__(self, id: int, user_id: int) -> None:
        self.id = id
        self.user_id = user_id


@pytest.fixture(autouse=True)
def _reset_gate():
    Gate._reset_for_tests()
    yield
    Gate._reset_for_tests()


async def test_gate_define_and_allows():
    Gate.define("view-metrics", lambda user: bool(user and user.is_admin))
    admin = _User(1, is_admin=True)
    member = _User(2, is_admin=False)
    assert await Gate.for_user(admin).allows("view-metrics") is True
    assert await Gate.for_user(member).allows("view-metrics") is False
    assert await Gate.for_user(member).denies("view-metrics") is True


async def test_gate_denies_guests_without_calling_the_callback_by_default():
    calls: list[object] = []

    def callback(user) -> bool:
        calls.append(user)
        return True

    Gate.define("secret", callback)
    assert await Gate.for_user(None).allows("secret") is False
    assert calls == []  # never called: the callback does not declare it accepts a guest


async def test_gate_allows_guests_when_annotated_optional():
    def callback(user: _User | None) -> bool:
        return user is None

    Gate.define("public-thing", callback)
    assert await Gate.for_user(None).allows("public-thing") is True


async def test_policy_convention_lookup(monkeypatch: pytest.MonkeyPatch):
    """`tests.auth._fake_models.post.Post` -> `tests.auth._fake_models.policies.post_policy.PostPolicy`."""
    models_pkg = types.ModuleType("tests.auth._fake_models")
    models_sub = types.ModuleType("tests.auth._fake_models.models")
    post_module = types.ModuleType("tests.auth._fake_models.models.post")

    class Post:
        pass

    post_module.Post = Post
    Post.__module__ = "tests.auth._fake_models.models.post"

    policies_module = types.ModuleType("tests.auth._fake_models.policies.post_policy")

    class PostPolicy:
        async def view(self, user: _User | None, post: Post) -> bool:
            return True

        async def update(self, user: _User, post: Post) -> bool:
            return user.id == getattr(post, "user_id", None)

    policies_module.PostPolicy = PostPolicy

    sys.modules["tests.auth._fake_models"] = models_pkg
    sys.modules["tests.auth._fake_models.models"] = models_sub
    sys.modules["tests.auth._fake_models.models.post"] = post_module
    sys.modules["tests.auth._fake_models.policies"] = types.ModuleType("tests.auth._fake_models.policies")
    sys.modules["tests.auth._fake_models.policies.post_policy"] = policies_module
    try:
        post = Post()
        post.user_id = 7
        owner = _User(7)
        stranger = _User(8)
        assert await Gate.for_user(owner).allows("update", post) is True
        assert await Gate.for_user(stranger).allows("update", post) is False
        # Guests are denied for `update` (no `| None`)...
        assert await Gate.for_user(None).allows("update", post) is False
        # ...but allowed to reach `view`, which declares `user: _User | None`.
        assert await Gate.for_user(None).allows("view", post) is True
    finally:
        for name in list(sys.modules):
            if name.startswith("tests.auth._fake_models"):
                del sys.modules[name]


async def test_explicit_policy_mapping_wins_over_convention():
    class Thing:
        pass

    class ThingPolicy:
        async def view(self, user: _User, thing: Thing) -> bool:
            return True

    Gate.policy(Thing, ThingPolicy)
    assert await Gate.for_user(_User(1)).allows("view", Thing()) is True


async def test_policy_before_short_circuits():
    class Thing:
        pass

    class ThingPolicy:
        async def before(self, user: _User, ability: str) -> bool | None:
            return True if user.is_admin else None

        async def view(self, user: _User, thing: Thing) -> bool:
            return False  # never reached for the admin

    Gate.policy(Thing, ThingPolicy)
    admin = _User(1, is_admin=True)
    member = _User(2, is_admin=False)
    assert await Gate.for_user(admin).allows("view", Thing()) is True
    assert await Gate.for_user(member).allows("view", Thing()) is False


async def test_missing_policy_or_ability_is_denied():
    class Unmapped:
        pass

    assert await Gate.for_user(_User(1)).allows("view", Unmapped()) is False

    class Thing:
        pass

    class ThingPolicy:
        async def view(self, user: _User) -> bool:
            return True

    Gate.policy(Thing, ThingPolicy)
    assert await Gate.for_user(_User(1)).allows("delete", Thing()) is False  # no such method


async def test_authorize_raises_authorization_exception_on_denial():
    Gate.define("locked", lambda user: False)
    with pytest.raises(AuthorizationException):
        await Gate.authorize("locked")


async def test_authorize_class_argument_for_create_style_checks():
    class Post:
        pass

    class PostPolicy:
        async def create(self, user: _User) -> bool:
            return True

    Gate.policy(Post, PostPolicy)
    assert await Gate.for_user(_User(1)).allows("create", Post) is True


async def test_authenticatable_can_and_cannot_delegate_to_gate():
    from fastogram.auth import Authenticatable

    class Post:
        def __init__(self, user_id: int) -> None:
            self.user_id = user_id

    class PostPolicy:
        async def update(self, user: _User, post: Post) -> bool:
            return user.id == post.user_id

    Gate.policy(Post, PostPolicy)

    class AuthUser(Authenticatable, _User):
        pass

    owner = AuthUser(1)
    post = Post(user_id=1)
    assert await owner.can("update", post) is True
    assert await owner.cannot("update", post) is False


def test_authenticatable_hides_password_and_remember_token_by_default():
    from fastogram.auth import Authenticatable

    assert Authenticatable.__hidden__ == ("password", "remember_token")
