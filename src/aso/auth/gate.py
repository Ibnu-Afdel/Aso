"""`Gate` (T-39, D-030): `define`/`allows`/`denies`/`policy`/`authorize`, policy `before()`.

Policies are plain classes (no base class) found by convention: `app.models.post.Post` ->
`app.policies.post_policy.PostPolicy`. An explicit `Gate.policy(Post, PostPolicy)` mapping wins
over the convention. Guests are denied without calling the policy (or gate) unless the ability
method's `user` parameter is annotated `User | None` (Laravel's rule).
"""

from __future__ import annotations

import importlib
import inspect
import re
import types
import typing
from collections.abc import Callable
from typing import Any, ClassVar

from aso.exceptions.types import AuthorizationException

__all__ = ["AuthorizationException", "Gate"]


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _policy_module_for(model_cls: type) -> str:
    """`app.models.post` -> `app.policies.post_policy` (D-030's convention)."""
    module = model_cls.__module__
    if ".models." in module:
        module = module.replace(".models.", ".policies.", 1)
    elif module.startswith("models."):
        module = "policies." + module[len("models.") :]
    head, _, leaf = module.rpartition(".")
    leaf = f"{leaf}_policy" if leaf else f"{_snake(model_cls.__name__)}_policy"
    return f"{head}.{leaf}" if head else leaf


def _allows_none(annotation: Any) -> bool:
    if annotation is inspect.Parameter.empty:
        return False
    if annotation is type(None):
        return True
    origin = typing.get_origin(annotation)
    if origin is typing.Union or isinstance(annotation, types.UnionType):
        return type(None) in typing.get_args(annotation)
    return False


def _accepts_guest(callback: Callable[..., Any]) -> bool:
    """Whether `callback`'s first (non-`self`) parameter is annotated to allow `None`.

    Resolves only *that* parameter's annotation (not `typing.get_type_hints(callback)` on the
    whole signature): a later parameter referencing a name the callback's module hasn't imported
    (or, in tests, a class defined locally) must not make this conservative by accident.
    """
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError):
        return False
    params = [p for p in sig.parameters.values() if p.name != "self"]
    if not params:
        return False
    annotation = params[0].annotation
    if isinstance(annotation, str):
        try:
            annotation = eval(annotation, getattr(callback, "__globals__", {}), None)  # noqa: S307
        except Exception:
            return False
    return _allows_none(annotation)


async def _call(callback: Callable[..., Any], *args: Any) -> Any:
    result = callback(*args)
    if inspect.isawaitable(result):
        result = await result
    return result


class _UserGate:
    """`Gate.for_user(user)`: check abilities for a specific user (`Authenticatable.can()`)."""

    def __init__(self, user: Any) -> None:
        self._user = user

    async def allows(self, ability: str, *args: Any) -> bool:
        return await Gate._check(self._user, ability, args)

    async def denies(self, ability: str, *args: Any) -> bool:
        return not await self.allows(ability, *args)


class Gate:
    """`Gate.define/allows/denies/policy/authorize` (T-39). Classmethods, like Laravel's facade."""

    _gates: ClassVar[dict[str, Callable[..., Any]]] = {}
    _policies: ClassVar[dict[type, type]] = {}
    _policy_cache: ClassVar[dict[type, type | None]] = {}

    @classmethod
    def define(cls, ability: str, callback: Callable[..., Any]) -> None:
        cls._gates[ability] = callback

    @classmethod
    def policy(cls, model_cls: type, policy_cls: type) -> None:
        cls._policies[model_cls] = policy_cls
        cls._policy_cache.pop(model_cls, None)

    @classmethod
    def for_user(cls, user: Any) -> _UserGate:
        return _UserGate(user)

    @classmethod
    async def allows(cls, ability: str, *args: Any) -> bool:
        from aso.auth.guard import auth

        return await cls._check(auth().user(), ability, args)

    @classmethod
    async def denies(cls, ability: str, *args: Any) -> bool:
        return not await cls.allows(ability, *args)

    @classmethod
    async def authorize(cls, ability: str, *args: Any) -> None:
        if not await cls.allows(ability, *args):
            raise AuthorizationException()

    # ------------------------------------------------------------ resolution

    @classmethod
    def _resolve_policy(cls, model_cls: type) -> type | None:
        explicit = cls._policies.get(model_cls)
        if explicit is not None:
            return explicit
        if model_cls in cls._policy_cache:
            return cls._policy_cache[model_cls]
        policy_cls: type | None = None
        try:
            module = importlib.import_module(_policy_module_for(model_cls))
            policy_cls = getattr(module, f"{model_cls.__name__}Policy", None)
        except ImportError:
            policy_cls = None
        cls._policy_cache[model_cls] = policy_cls
        return policy_cls

    @classmethod
    async def _check(cls, user: Any, ability: str, args: tuple[Any, ...]) -> bool:
        if ability in cls._gates:
            callback = cls._gates[ability]
            if user is None and not _accepts_guest(callback):
                return False
            return bool(await _call(callback, user, *args))

        subject = args[0] if args else None
        model_cls = subject if isinstance(subject, type) else (type(subject) if subject is not None else None)
        if model_cls is None:
            return False
        policy_cls = cls._resolve_policy(model_cls)
        if policy_cls is None:
            return False
        method = getattr(policy_cls, ability, None)
        if method is None or not callable(method):
            return False
        if user is None and not _accepts_guest(method):
            return False
        policy = policy_cls()
        before = getattr(policy, "before", None)
        if before is not None:
            result = await _call(before, user, ability)
            if result is True:
                return True
            if result is False:
                return False
        bound = getattr(policy, ability)
        # `authorize("create", Post)` (a bare class, no instance yet): nothing to pass besides
        # `user` -- Laravel's `create(User $user)` takes no second parameter either. An instance
        # (or several arguments) is forwarded as given: `authorize("update", post)` ->
        # `update(user, post)`.
        call_args = () if len(args) == 1 and isinstance(args[0], type) else args
        return bool(await _call(bound, user, *call_args))

    @classmethod
    def _reset_for_tests(cls) -> None:
        cls._gates = {}
        cls._policies = {}
        cls._policy_cache = {}
