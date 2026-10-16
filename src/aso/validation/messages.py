"""Pydantic v2 errors -> Laravel rule keys and English messages (T-19), proven by spike S-3.

Also used by the async `Annotated` rules (`aso.validation.rules`): `render()` renders any
rule key through the same custom-message / `:placeholder` machinery, given a synthetic `err`-like
dict (`{"ctx": {...}}`) in place of a real Pydantic error.
"""

from __future__ import annotations

import typing
from typing import Any

from pydantic import BaseModel, EmailStr, ValidationError

# (pydantic type) -> (laravel rule, variant)  variant picks the message for min/max
TYPE_MAP: dict[str, tuple[str, str | None]] = {
    "missing": ("required", None),
    "string_too_short": ("min", "string"),
    "string_too_long": ("max", "string"),
    "too_short": ("min", "array"),
    "too_long": ("max", "array"),
    "greater_than_equal": ("min", "numeric"),
    "less_than_equal": ("max", "numeric"),
    "greater_than": ("gt", "numeric"),
    "less_than": ("lt", "numeric"),
    "int_parsing": ("integer", None),
    "int_type": ("integer", None),
    "int_from_float": ("integer", None),
    "float_parsing": ("numeric", None),
    "float_type": ("numeric", None),
    "decimal_parsing": ("numeric", None),
    "decimal_type": ("numeric", None),
    "bool_parsing": ("boolean", None),
    "bool_type": ("boolean", None),
    "string_type": ("string", None),
    "literal_error": ("in", None),
    "enum": ("in", None),
    "url_parsing": ("url", None),
    "url_type": ("url", None),
    "url_scheme": ("url", None),
    "string_pattern_mismatch": ("regex", None),
    "list_type": ("array", None),
    "multiple_of": ("multiple_of", None),
}
PREFIX_MAP = {"date_": "date", "datetime_": "date", "uuid_": "uuid", "decimal_": "numeric"}

# Laravel lang/en/validation.php wording, plus the async-rule keys (confirmed/unique/exists/...).
MESSAGES: dict[str, str | dict[str, str]] = {
    "required": "The :attribute field is required.",
    "min": {
        "string": "The :attribute field must be at least :min characters.",
        "numeric": "The :attribute field must be at least :min.",
        "array": "The :attribute field must have at least :min items.",
    },
    "max": {
        "string": "The :attribute field must not be greater than :max characters.",
        "numeric": "The :attribute field must not be greater than :max.",
        "array": "The :attribute field must not have more than :max items.",
        "file": "The :attribute field must not be greater than :max kilobytes.",
    },
    "gt": {"numeric": "The :attribute field must be greater than :value."},
    "lt": {"numeric": "The :attribute field must be less than :value."},
    "integer": "The :attribute field must be an integer.",
    "numeric": "The :attribute field must be a number.",
    "boolean": "The :attribute field must be true or false.",
    "string": "The :attribute field must be a string.",
    "array": "The :attribute field must be an array.",
    "email": "The :attribute field must be a valid email address.",
    "url": "The :attribute field must be a valid URL.",
    "date": "The :attribute field must be a valid date.",
    "regex": "The :attribute field format is invalid.",
    "in": "The selected :attribute is invalid.",
    "uuid": "The :attribute field must be a valid UUID.",
    "multiple_of": "The :attribute field must be a multiple of :value.",
    "confirmed": "The :attribute field confirmation does not match.",
    "unique": "The :attribute has already been taken.",
    "exists": "The selected :attribute is invalid.",
    "accepted": "The :attribute field must be accepted.",
    "current_password": "The :attribute field is incorrect.",
    "file": "The :attribute field must be a file.",
    "mimes": "The :attribute field must be a file of type: :values.",
    "image": "The :attribute field must be an image.",
    "password_letters": "The :attribute field must contain at least one letter.",
    "password_mixed_case": "The :attribute field must contain at least one uppercase and one lowercase letter.",
    "password_numbers": "The :attribute field must contain at least one number.",
    "password_symbols": "The :attribute field must contain at least one symbol.",
    "invalid": "The :attribute field is invalid.",
}


def _is_email_field(model: type[BaseModel], loc: tuple[Any, ...]) -> bool:
    """Walk the model's annotations along `loc` and check whether the leaf is EmailStr."""
    current: Any = model
    for part in loc:
        if isinstance(part, int):
            continue
        if isinstance(current, type) and issubclass(current, BaseModel) and part in current.model_fields:
            ann = current.model_fields[part].annotation
            current = _unwrap(ann)
        else:
            return False
    return current is EmailStr or getattr(current, "__name__", "") == "EmailStr"


def _unwrap(ann: Any) -> Any:
    origin = typing.get_origin(ann)
    if origin is typing.Annotated:
        return _unwrap(typing.get_args(ann)[0])
    if origin in (list, set, tuple):
        return _unwrap(typing.get_args(ann)[0])
    if origin is typing.Union or str(origin) == "<class 'types.UnionType'>":
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        return _unwrap(args[0]) if len(args) == 1 else ann
    return ann


def rule_for(err: dict[str, Any], model: type[BaseModel]) -> tuple[str, str | None]:
    t = err["type"]
    if t in TYPE_MAP:
        return TYPE_MAP[t]
    for prefix, rule in PREFIX_MAP.items():
        if t.startswith(prefix):
            return rule, None
    if t == "value_error":
        if _is_email_field(model, err["loc"]):
            return "email", None
        return "__value_error__", None
    return "invalid", None


def dot_key(loc: tuple[Any, ...]) -> str:
    return ".".join(str(p) for p in loc)


def attribute_name(key: str, attributes: dict[str, str]) -> str:
    if key in attributes:
        return attributes[key]
    last = key.split(".")[-1]
    return attributes.get(last, last.replace("_", " "))


def render(
    rule: str,
    variant: str | None,
    err: dict[str, Any],
    key: str,
    custom: dict[str, str],
    attributes: dict[str, str],
) -> str:
    """Render one message: `messages()` override (`"<key>.<rule>"` then `"<key>"`), else the
    built-in English table, with `:attribute`/`:min`/`:max`/`:value`/`:values` filled in.

    `err` is either a real Pydantic error dict (with `loc`/`ctx`/`input`) or a synthetic one built
    by an async rule (`{"ctx": {...}}`), so both call sites share this one renderer.
    """
    template = custom.get(f"{key}.{rule}") or custom.get(key)
    if template is None:
        if rule == "__value_error__":
            return str(err.get("ctx", {}).get("error", "The :attribute field is invalid."))
        entry = MESSAGES.get(rule, MESSAGES["invalid"])
        template = entry[variant or "numeric"] if isinstance(entry, dict) else entry
    ctx = err.get("ctx", {}) or {}
    values = ctx.get("values")
    repl = {
        ":attribute": attribute_name(key, attributes),
        ":min": str(ctx.get("min_length", ctx.get("ge", ctx.get("min", "")))),
        ":max": str(ctx.get("max_length", ctx.get("le", ctx.get("max", "")))),
        ":value": str(ctx.get("gt", ctx.get("lt", ctx.get("multiple_of", ctx.get("value", err.get("input", "")))))),
        ":values": ", ".join(str(v) for v in values) if values else "",
    }
    for placeholder in sorted(repl, key=len, reverse=True):  # ":values" before ":value"
        template = template.replace(placeholder, repl[placeholder])
    return template


def required_errors(
    model: type[BaseModel],
    data: dict[str, Any],
    custom: dict[str, str] | None = None,
    attributes: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """Step 5: a `required` error for every field without a default whose value is missing/None
    and whose type does not allow `None` (so an empty string behaves like Laravel's `required`)."""
    custom, attributes = custom or {}, attributes or {}
    errors: dict[str, list[str]] = {}
    for name, field in model.model_fields.items():
        if field.is_required() and data.get(name) is None:
            allows_none = type(None) in typing.get_args(field.annotation)
            if not allows_none:
                errors.setdefault(name, []).append(render("required", None, {}, name, custom, attributes))
    return errors


def validate(
    model: type[BaseModel],
    data: dict[str, Any],
    custom: dict[str, str] | None = None,
    attributes: dict[str, str] | None = None,
) -> tuple[BaseModel | None, dict[str, list[str]]]:
    """Sync-only helper kept for the spike's own tests: required pre-check + Pydantic validation.

    `FormRequest.resolve()` no longer calls this directly (it needs the required errors and the
    Pydantic errors as separate steps so it can run the async rules in between); it is kept here
    as the smallest piece other code or tests can reach for a plain model.
    """
    custom, attributes = custom or {}, attributes or {}
    errors = required_errors(model, data, custom, attributes)
    try:
        obj = model.model_validate(data)
    except ValidationError as e:
        obj = None
        for err in e.errors():
            key = dot_key(err["loc"])
            if key in errors:  # already 'required'
                continue
            rule, variant = rule_for(err, model)
            errors.setdefault(key, []).append(render(rule, variant, err, key, custom, attributes))
    return (obj if not errors else None), errors
