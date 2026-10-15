"""`Factory`: Faker-backed model factories (T-36).

```python
class PostFactory(Factory):
    model = Post

    def definition(self) -> dict:
        return {"title": self.faker.sentence()}

post = await PostFactory.new().create()
posts = await PostFactory.new().count(5).published().create()
```

Factories bypass `Model.__fillable__` (`definition()`/`state()`/overrides are set with plain
`setattr`, not `Model.fill()`/`Model.create()`), same as Laravel's factories: test data routinely
sets columns a form may not (`email_verified_at`, `user_id`). Unknown attribute names still raise
`AttributeError`, matching T-36's "How it works" #4.
"""

from __future__ import annotations

import copy
import re
from typing import Any, ClassVar, Self

from sqlalchemy import inspect as sa_inspect

__all__ = ["Factory", "factory_for"]


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _faker_locale() -> str:
    from fastogram.config import config

    return config("app.faker_locale", "en_US")


def _valid_attrs(model_cls: type) -> set[str]:
    """Column attribute names + relationship names a factory is allowed to `setattr` (mirrors
    `Model.fill()`'s own validity check, T-31)."""
    mapper = sa_inspect(model_cls)
    return {prop.key for prop in mapper.column_attrs} | set(mapper.relationships.keys())


def factory_for(model: type) -> type[Factory]:
    """`app.models.user.User` -> `database.factories.user_factory.UserFactory` (T-36 model <->
    factory lookup by convention)."""
    import importlib

    module_name = f"database.factories.{_snake(model.__name__)}_factory"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f'No factory found for {model.__name__} (expected database/factories/{_snake(model.__name__)}_factory.py). '
            f"Generate one with `fastogram make:factory {model.__name__}Factory --model={model.__name__}`."
        ) from exc
    class_name = f"{model.__name__}Factory"
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise RuntimeError(f'Module "{module_name}" has no class "{class_name}".') from exc


class Factory:
    """Subclass this, set `model` and implement `definition()`."""

    model: ClassVar[type[Any]]

    def __init__(self) -> None:
        self._states: list[Any] = []
        self._count: int = 1
        self._relations: dict[str, Any] = {}  # relation name -> count or a configured Factory
        self._for: dict[str, Any] = {}  # relation name -> an existing model instance
        from faker import Faker

        self.faker = Faker(_faker_locale())

    # ------------------------------------------------------------ construction

    @classmethod
    def new(cls) -> Self:
        return cls()

    def definition(self) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement definition().")

    # ------------------------------------------------------------ fluent configuration (each returns a clone)

    def _clone(self) -> Self:
        clone = copy.copy(self)
        clone._states = list(self._states)
        clone._relations = dict(self._relations)
        clone._for = dict(self._for)
        return clone

    def count(self, n: int) -> Self:
        clone = self._clone()
        clone._count = n
        return clone

    def state(self, attributes: dict[str, Any] | Any) -> Self:
        """`self.state({...})` (a dict, or a callable taking the factory and returning a dict)."""
        clone = self._clone()
        clone._states = [*clone._states, attributes]
        return clone

    def __getattr__(self, name: str) -> Any:
        # Only reached once normal attribute lookup fails, so this never shadows `state()`,
        # `count()`, a named state method, or anything else defined on the class.
        if name.startswith("has_"):
            relation = name[len("has_") :]
            return lambda count_or_factory=1: self._with_has(relation, count_or_factory)
        if name.startswith("for_"):
            relation = name[len("for_") :]
            return lambda model: self._with_for(relation, model)
        raise AttributeError(name)

    def _with_has(self, relation: str, count_or_factory: Any) -> Self:
        clone = self._clone()
        clone._relations[relation] = count_or_factory
        return clone

    def _with_for(self, relation: str, model: Any) -> Self:
        clone = self._clone()
        clone._for[relation] = model
        return clone

    # ------------------------------------------------------------ resolving attributes

    def _resolve_attributes(self, overrides: dict[str, Any]) -> dict[str, Any]:
        attrs = dict(self.definition())
        for state in self._states:
            extra = state(self) if callable(state) else state
            attrs.update(extra)
        for relation, model in self._for.items():
            attrs[f"{relation}_id"] = getattr(model, "id", model)
        attrs.update(overrides)
        return attrs

    def _build_one(self, overrides: dict[str, Any]) -> Any:
        attrs = self._resolve_attributes(overrides)
        instance = self.model()
        valid = _valid_attrs(type(instance))
        for key, value in attrs.items():
            if key not in valid:
                raise AttributeError(f"{type(instance).__name__} has no column or relation {key!r}.")
            setattr(instance, key, value)
        return instance

    # ------------------------------------------------------------ make (in-memory, synchronous)

    def make(self, **overrides: Any) -> Any:
        if self._count == 1:
            return self._build_one(overrides)
        return [self._build_one(overrides) for _ in range(self._count)]

    # ------------------------------------------------------------ create (persisted, asynchronous)

    async def create(self, **overrides: Any) -> Any:
        if self._count == 1:
            return await self._create_one(overrides)
        return [await self._create_one(overrides) for _ in range(self._count)]

    async def _create_one(self, overrides: dict[str, Any]) -> Any:
        instance = self._build_one(overrides)
        await instance.save()
        await self._create_relations(instance)
        return instance

    async def _create_relations(self, parent: Any) -> None:
        """`has_<relation>(n)` (T-36 "How it works" #5): after the parent is saved, find the
        related model through the `has_many`/`has_one` relation, load its factory by convention,
        and create the children with the paired `belongs_to`'s foreign key set."""
        mapper = sa_inspect(type(parent)).mapper
        for relation, spec in self._relations.items():
            relationship = mapper.relationships.get(relation)
            if relationship is None:
                raise AttributeError(f"{type(parent).__name__} has no relation {relation!r}.")
            child_model = relationship.mapper.class_
            factory = self._resolve_relation_factory(child_model, spec)
            back_populates = relationship.back_populates
            if back_populates:
                factory = getattr(factory, f"for_{back_populates}")(parent)
            else:
                fk_name = f"{_snake(type(parent).__name__)}_id"
                factory = factory.state({fk_name: parent.id})
            await factory.create()

    def _resolve_relation_factory(self, model: type, spec: Any) -> Factory:
        if isinstance(spec, Factory):
            return spec
        return factory_for(model).new().count(int(spec))
