"""`FormRequest`: Pydantic form requests with Laravel's hooks (T-19).

`resolve()` runs the ten steps from the guide's "How it works" section, in order: collect input,
clean it up, build an unvalidated context instance, `prepare_for_validation()` + `authorize()`,
a `required` pre-check, Pydantic validation (mapped to Laravel rule keys/messages), the async
`Annotated` rules, `after()`, then either raise `ValidationException` or return the instance.

The route compiler (T-13) injects this as `Depends(StorePostRequest.resolve)`; because it is a
dependency (not the endpoint's body parameter), and `resolve`'s own signature takes a plain
`Request`, FastAPI never turns a `FormRequest` subclass into a request-body schema.
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, PrivateAttr, ValidationError
from starlette.requests import Request as StarletteRequest

from aso.exceptions.types import ValidationException
from aso.validation.input import clean_input, collect_input
from aso.validation.messages import dot_key, render, required_errors, rule_for
from aso.validation.rules import Rule

__all__ = ["FormRequest", "old", "validate"]

#: Field names that would shadow a `FormRequest` hook or accessor. `__pydantic_init_subclass__`
#: rejects a subclass that declares one of these as a field.
RESERVED_NAMES = frozenset(
    {
        "user",
        "request",
        "route",
        "input",
        "merge",
        "validated",
        "messages",
        "attributes",
        "authorize",
        "after",
        "redirect",
        "redirect_route",
        "error_bag",
        "add_error",
        "prepare_for_validation",
        "resolve",
    }
)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class FormRequest(BaseModel):
    """A Pydantic `BaseModel` with Laravel's form-request hooks (T-19, D-008)."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    error_bag: ClassVar[str] = "default"
    redirect: ClassVar[str | None] = None
    redirect_route: ClassVar[str | None] = None

    _request: Any = PrivateAttr(default=None)
    _input: dict[str, Any] = PrivateAttr(default_factory=dict)
    _errors: dict[str, list[str]] = PrivateAttr(default_factory=dict)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        shadowed = sorted(RESERVED_NAMES & set(cls.model_fields))
        if shadowed:
            name = shadowed[0]
            raise TypeError(
                f'{cls.__name__}.{name} shadows the FormRequest hook/accessor `{name}`. Rename the '
                f'attribute, or if the submitted input is really named "{name}", keep a different '
                f'Python name and write `{name}_: Annotated[..., Field(alias="{name}")]`.'
            )

    # ------------------------------------------------------------ hooks (override in subclasses)

    def prepare_for_validation(self) -> None:
        """Runs once, before `authorize()`. Override to call `self.merge({...})`."""

    async def authorize(self) -> bool:
        """Runs after `prepare_for_validation()`. `False` raises `AuthorizationException` (403)."""
        return True

    def messages(self) -> dict[str, str]:
        """`{"title.required": "...", "title": "..."}` overrides, Laravel rule-key style."""
        return {}

    def attributes(self) -> dict[str, str]:
        """`{"published_at": "publish date"}` — custom `:attribute` names."""
        return {}

    async def after(self) -> None:
        """Runs only when every field is valid. Override to call `self.add_error(...)`."""

    # ------------------------------------------------------------ accessors (available in hooks)

    @property
    def request(self) -> Any:
        return self._request

    def user(self) -> Any:
        from aso.auth import auth

        return auth().user()

    def route(self, name: str | None = None, default: Any = None) -> Any:
        """Route parameters / bound models: `context.current().route_params` + the request's own
        path params (the latter as a fallback, while the routing package's binding step lands)."""
        from aso import context

        params: dict[str, Any] = {}
        ctx = context.current()
        if ctx is not None:
            params.update(ctx.route_params or {})
        if self._request is not None:
            params.update(dict(self._request.path_params))
        if name is None:
            return params
        return params.get(name, default)

    def input(self, key: str | None = None, default: Any = None) -> Any:
        """The cleaned input (step 2): trimmed, empty strings turned into `None`."""
        if key is None:
            return self._input
        return self._input.get(key, default)

    def merge(self, data: dict[str, Any]) -> None:
        self._input.update(data)

    def add_error(self, field: str, message: str) -> None:
        self._errors.setdefault(field, []).append(message)

    def validated(self, key: str | None = None, default: Any = None) -> Any:
        """`model_dump()` minus `*_confirmation` keys; `validated("title")` for one value."""
        data = {k: v for k, v in self.model_dump().items() if not k.endswith("_confirmation")}
        return data if key is None else data.get(key, default)

    # ------------------------------------------------------------ resolution (T-13 injects this)

    @classmethod
    async def resolve(cls, request: StarletteRequest) -> FormRequest:
        from aso import context
        from aso.exceptions.types import AuthorizationException

        ctx = context.current()
        if ctx is not None and ctx.request is not None:
            request = ctx.request

        raw = await collect_input(request)  # 1. collect input
        data = clean_input(raw)  # 2. clean up

        obj = cls.model_construct()  # 3. context instance
        obj._request = request
        obj._input = data
        obj._errors = {}

        obj.prepare_for_validation()  # 4. prepare, then authorize
        data = obj._input
        if not await _maybe_await(obj.authorize()):
            raise AuthorizationException()

        custom, attributes = obj.messages(), obj.attributes()

        errors = required_errors(cls, data, custom, attributes)  # 5. required pre-check

        try:  # 6. Pydantic validation
            validated = cls.model_validate(data)
        except ValidationError as exc:
            validated = None
            for err in exc.errors():
                key = dot_key(err["loc"])
                if key in errors:  # already a required error
                    continue
                rule, variant = rule_for(err, cls)
                errors.setdefault(key, []).append(render(rule, variant, err, key, custom, attributes))

        if validated is not None:
            validated._request = request
            validated._input = data
            validated._errors = {}

            for name, field in cls.model_fields.items():  # 7. async Annotated rules
                if name in errors:
                    continue
                rules = [m for m in field.metadata if isinstance(m, Rule)]
                if not rules:
                    continue
                value = getattr(validated, name)
                if value is None:  # optional field left empty: skip its rules (Laravel "nullable")
                    continue
                for rule in rules:  # one at a time
                    message = await rule.check(value, field=name, form=validated)
                    if message:
                        errors.setdefault(name, []).append(message)

            if not errors:  # 8. after(), only when nothing has failed
                await _maybe_await(validated.after())
                for field_name, messages_ in validated._errors.items():
                    errors.setdefault(field_name, []).extend(messages_)

        if errors:  # 9. raise on errors
            redirect_to = cls.redirect
            if redirect_to is None and cls.redirect_route:
                from aso.routing import route as route_url

                redirect_to = route_url(cls.redirect_route)
            raise ValidationException(errors, bag=cls.error_bag, redirect_to=redirect_to, input=raw)

        assert validated is not None  # 10. success
        return validated


async def validate(
    request: StarletteRequest,
    fields: dict[str, Any],
    *,
    error_bag: str = "default",
    redirect: str | None = None,
    redirect_route: str | None = None,
) -> Any:
    """A one-off form request without a class: `validate(request, {"q": (str, Field(max_length=100))})`.

    Behaves exactly like a form request (redirects back with errors / 422 JSON on failure).
    """
    from pydantic import create_model

    model = create_model("_AdHocFormRequest", __base__=FormRequest, **fields)
    model.error_bag = error_bag
    model.redirect = redirect
    model.redirect_route = redirect_route
    return await model.resolve(request)


def old(key: str | None = None, default: Any = None) -> Any:
    """The input flashed by a failed validation (`_old_input`), for plain Jinja templates (T-19).

    LARAVEL-MAP §5 lists `old()` next to `csrf_token()`/`csrf_field()` under the HTTP bullet; it is
    implemented here because `_old_input` is validation's own flash key (written by the exception
    handler from `ValidationException.input`), and `aso.http` can re-export it the same way
    it already re-exports `FormRequest` from this package.
    """
    from aso.exceptions.types import SessionUnavailable
    from aso.session import session

    try:
        data = session().get("_old_input") or {}
    except SessionUnavailable:
        return default
    if key is None:
        return data
    return data.get(key, default)
