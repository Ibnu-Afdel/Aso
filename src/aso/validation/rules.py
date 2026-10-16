"""Async validation rules carried as `Annotated[...]` metadata (T-19).

`FormRequest.resolve()` runs these **one at a time**, only for fields that passed Pydantic
validation (step 6). Each rule's `check()` returns the rendered error message, or `None` when the
value passes.

`Unique`/`Exists` query the request's DB session (`aso.database.DB.scalar`) with a bound
parameter for the *value* and a hand-written, identifier-checked table/column name: SQL has no
placeholder syntax for identifiers, so table and column names are validated against a strict
pattern instead of ever being taken from user input.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from aso.validation.messages import render
from aso.validation.uploaded_file import UploadedFile

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(name: str, what: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(
            f"Invalid {what} name for a validation rule: {name!r}. Table and column names must be "
            "plain identifiers (letters, digits, underscore); they are never interpolated from "
            "user input."
        )
    return name


class Rule:
    """Base class for an async validation rule used in `Annotated[...]` metadata."""

    rule_name: str = "invalid"

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        """Return a rendered error message, or `None` if `value` passes."""
        raise NotImplementedError

    def default_message(self, field: str, form: Any, variant: str | None = None, ctx: dict[str, Any] | None = None) -> str:
        return render(self.rule_name, variant, {"ctx": ctx or {}}, field, form.messages(), form.attributes())


class Confirmed(Rule):
    """`password_confirmation` must equal `password` (Laravel's `confirmed`)."""

    rule_name = "confirmed"

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        confirmation = form.input(f"{field}_confirmation")
        return None if confirmation == value else self.default_message(field, form)


class Unique(Rule):
    """`unique:table,column` — fails when a matching row already exists."""

    rule_name = "unique"

    def __init__(self, table: str, column: str | None = None, *, ignore: Callable[[Any], Any] | None = None) -> None:
        self.table = _identifier(table, "table")
        self.column = _identifier(column, "column") if column else None
        self.ignore = ignore

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        from aso.database import DB

        column = _identifier(self.column or field, "column")
        sql = f"SELECT 1 FROM {self.table} WHERE {column} = :v"  # noqa: S608 (identifiers validated above)
        bindings: dict[str, Any] = {"v": value}
        ignore_id = self.ignore(form) if self.ignore is not None else None
        if ignore_id is not None:  # `id <> NULL` is never true, so a None id must ignore nothing
            sql += " AND id <> :ignore_id"
            bindings["ignore_id"] = ignore_id
        sql += " LIMIT 1"
        row = await DB.scalar(sql, bindings)
        return None if row is None else self.default_message(field, form)


class Exists(Rule):
    """`exists:table,column` — fails when no matching row exists."""

    rule_name = "exists"

    def __init__(self, table: str, column: str = "id") -> None:
        self.table = _identifier(table, "table")
        self.column = _identifier(column, "column")

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        from aso.database import DB

        sql = f"SELECT 1 FROM {self.table} WHERE {self.column} = :v LIMIT 1"  # noqa: S608
        row = await DB.scalar(sql, {"v": value})
        return None if row is not None else self.default_message(field, form)


class CurrentPassword(Rule):
    """The value must hash-match the current user's password."""

    rule_name = "current_password"

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        try:
            from aso.auth import auth
        except ImportError as exc:  # pragma: no cover - auth always ships with the framework
            raise RuntimeError("CurrentPassword needs aso.auth, which is not available.") from exc
        user = auth().user()
        if user is None:
            return self.default_message(field, form)
        try:
            from aso.security.hash import check as check_hash  # type: ignore[import-not-found]
        except ImportError as exc:
            raise NotImplementedError(
                "CurrentPassword needs aso.security.hash, which is not implemented yet."
            ) from exc
        return None if check_hash(value, getattr(user, "password", "")) else self.default_message(field, form)


class Accepted(Rule):
    """Laravel's `accepted`: `True`/`1`/`"1"`/`"yes"`/`"on"`/`"true"` (case-insensitive)."""

    rule_name = "accepted"
    TRUE_VALUES = {True, "1", "yes", "on", "true"}

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        v = value.lower() if isinstance(value, str) else value
        return None if v in self.TRUE_VALUES else self.default_message(field, form)


class File(Rule):
    """`file`/`mimes:.../max:...` (kilobytes), for an `Annotated[UploadedFile, File(...)]` field."""

    rule_name = "file"

    def __init__(self, max_kb: int | None = None, mimes: list[str] | None = None) -> None:
        self.max_kb = max_kb
        self.mimes = [m.lower() for m in mimes] if mimes else None

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        if not isinstance(value, UploadedFile):
            return self.default_message(field, form)
        if self.mimes is not None and value.extension() not in self.mimes:
            return render("mimes", None, {"ctx": {"values": self.mimes}}, field, form.messages(), form.attributes())
        if self.max_kb is not None and value.size > self.max_kb * 1024:
            return render("max", "file", {"ctx": {"max": self.max_kb}}, field, form.messages(), form.attributes())
        return None


class Image(Rule):
    """`image` — a `File` restricted to common image extensions."""

    rule_name = "image"
    MIMES = ("jpg", "jpeg", "png", "gif", "bmp", "svg", "webp")

    def __init__(self, max_kb: int | None = None) -> None:
        self.max_kb = max_kb

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        if not isinstance(value, UploadedFile) or value.extension() not in self.MIMES:
            return self.default_message(field, form)
        if self.max_kb is not None and value.size > self.max_kb * 1024:
            return render("max", "file", {"ctx": {"max": self.max_kb}}, field, form.messages(), form.attributes())
        return None


class Password(Rule):
    """`Password.min(n).letters().mixed_case().numbers().symbols()` / `Password.defaults()`."""

    rule_name = "password"

    def __init__(self) -> None:
        self._min = 8
        self._letters = False
        self._mixed_case = False
        self._numbers = False
        self._symbols = False

    def min(self, n: int) -> Password:
        self._min = n
        return self

    def letters(self) -> Password:
        self._letters = True
        return self

    def mixed_case(self) -> Password:
        self._mixed_case = True
        return self

    def numbers(self) -> Password:
        self._numbers = True
        return self

    def symbols(self) -> Password:
        self._symbols = True
        return self

    @classmethod
    def defaults(cls) -> Password:
        """The app-wide default, from `config("auth.password_defaults")` (T-38).

        That config value may be a ready-made `Password` or a zero-argument callable returning
        one (Laravel's `Password::defaults(fn () => ...)`). Falls back to `min(8)` + letters +
        mixed case + numbers when no `config/auth.py` is loaded (e.g. in isolated unit tests).
        """
        from aso.config import config

        configured = config("auth.password_defaults")
        if isinstance(configured, Password):
            return configured
        if callable(configured):
            result = configured()
            if isinstance(result, Password):
                return result
        return cls().min(8).letters().mixed_case().numbers()

    async def check(self, value: Any, *, field: str, form: Any) -> str | None:
        if not isinstance(value, str):
            return self.default_message(field, form)
        if len(value) < self._min:
            return render("min", "string", {"ctx": {"min_length": self._min}}, field, form.messages(), form.attributes())
        checks = [
            (self._letters, "password_letters", re.search(r"[A-Za-z]", value)),
            (self._mixed_case, "password_mixed_case", re.search(r"[a-z]", value) and re.search(r"[A-Z]", value)),
            (self._numbers, "password_numbers", re.search(r"\d", value)),
            (self._symbols, "password_symbols", re.search(r"[^A-Za-z0-9]", value)),
        ]
        for enabled, rule_key, matched in checks:
            if enabled and not matched:
                return render(rule_key, None, {"ctx": {}}, field, form.messages(), form.attributes())
        return None


__all__ = [
    "Accepted",
    "Confirmed",
    "CurrentPassword",
    "Exists",
    "File",
    "Image",
    "Password",
    "Rule",
    "Unique",
]
