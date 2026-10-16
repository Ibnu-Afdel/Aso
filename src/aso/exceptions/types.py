"""Every framework exception, defined in one place.

Packages re-export them at the import paths in LARAVEL-MAP §3 (for example
`aso.database.ModelNotFound`). Defining them here lets the exception handler (T-20) and
the packages built in parallel depend on one module instead of on each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from starlette.exceptions import HTTPException as StarletteHTTPException

HTTP_MESSAGES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    410: "Gone",
    413: "Content Too Large",
    419: "Page Expired",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Server Error",
    503: "Service Unavailable",
}


# ---------------------------------------------------------------- HTTP


class HttpException(StarletteHTTPException):
    """Raised by `abort()`. Subclasses Starlette's so FastAPI code raising it is handled too."""

    def __init__(self, status_code: int, message: str = "", headers: Mapping[str, str] | None = None) -> None:
        super().__init__(status_code=status_code, detail=message or HTTP_MESSAGES.get(status_code, ""), headers=headers)
        self.message = message

    @property
    def status(self) -> int:
        return self.status_code


class TokenMismatchException(HttpException):
    """CSRF token missing or wrong (T-12). Rendered as redirect-back (Inertia) or 419."""

    def __init__(self, message: str = "CSRF token mismatch.") -> None:
        super().__init__(419, message)


class InvalidSignatureException(HttpException):
    def __init__(self, message: str = "Invalid signature.") -> None:
        super().__init__(403, message)


class ThrottleRequestsException(HttpException):
    def __init__(self, retry_after: int, message: str = "Too Many Attempts.", headers: Mapping[str, str] | None = None) -> None:
        merged = {"Retry-After": str(retry_after), **(headers or {})}
        super().__init__(429, message, merged)
        self.retry_after = retry_after


class RequestBodyTooLarge(HttpException):
    def __init__(self, limit: int) -> None:
        super().__init__(
            413,
            f"The request body is larger than config('app.max_buffered_body') ({limit} bytes). "
            "Stream it in the controller instead of reading it in middleware.",
        )


# ---------------------------------------------------------------- auth


class AuthenticationException(Exception):
    """Not logged in (T-38). Web: redirect to `login`; API: 401 JSON."""

    def __init__(self, message: str = "Unauthenticated.", guards: list[str] | None = None, redirect_to: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.guards = guards or []
        self.redirect_to = redirect_to


class AuthorizationException(Exception):
    """A policy, gate or `authorize()` said no (T-39). Rendered as 403."""

    status_code = 403

    def __init__(self, message: str = "This action is unauthorized.", status: int = 403) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status


# ---------------------------------------------------------------- validation


class ValidationException(Exception):
    """Validation failed (T-19).

    `errors` maps dot keys to **all** messages for that key. The web renderer flashes them under
    `errors.<bag>` and redirects; the API renderer answers 422 with Laravel's JSON shape.
    """

    status_code = 422

    def __init__(
        self,
        errors: Mapping[str, list[str] | str],
        bag: str = "default",
        redirect_to: str | None = None,
        input: Mapping[str, Any] | None = None,
    ) -> None:
        self.errors: dict[str, list[str]] = {k: [v] if isinstance(v, str) else list(v) for k, v in errors.items()}
        self.bag = bag
        self.redirect_to = redirect_to
        self.input = dict(input) if input is not None else None
        super().__init__(self.summary())

    def summary(self) -> str:
        messages = [m for msgs in self.errors.values() for m in msgs]
        if not messages:
            return "The given data was invalid."
        first = messages[0]
        rest = len(messages) - 1
        if rest:
            return f"{first} (and {rest} more error{'s' if rest > 1 else ''})"
        return first

    @classmethod
    def with_messages(cls, messages: Mapping[str, list[str] | str], bag: str = "default") -> ValidationException:
        return cls(messages, bag=bag)


# ---------------------------------------------------------------- database


class ModelNotFound(Exception):
    status_code = 404

    def __init__(self, model: str, ids: Any = None) -> None:
        self.model = model
        self.ids = ids
        if ids is None or ids == []:
            message = f"No query results for model [{model}]."
        else:
            shown = ", ".join(str(i) for i in ids) if isinstance(ids, (list, tuple)) else str(ids)
            message = f"No query results for model [{model}] {shown}."
        super().__init__(message)
        self.message = message


class MultipleRecordsFound(Exception):
    def __init__(self, count: int) -> None:
        super().__init__(f"{count} records were found.")
        self.count = count


class MassAssignmentError(Exception):
    pass


class LazyLoadingViolation(RuntimeError):
    def __init__(self, model: str, relation: str) -> None:
        super().__init__(
            f"Attempted to lazy load [{relation}] on model [{model}]. "
            f'Eager load it with {model}.with_("{relation}") or `await model.load("{relation}")`.'
        )
        self.model = model
        self.relation = relation


# ---------------------------------------------------------------- session, inertia, security, queue


class SessionUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "There is no session here. session() only works during a request in the `web` group "
            "(not in API routes, jobs or CLI commands)."
        )


class SessionTooLarge(RuntimeError):
    pass


class PageNotFound(Exception):
    """`inertia("x/y")` named a page file that does not exist (local/testing only)."""

    status_code = 500

    def __init__(self, component: str, expected_path: str) -> None:
        super().__init__(f'Inertia page [{component}] not found. Expected the file "{expected_path}". '
                         f"Create it with `aso make:page {component}`.")
        self.component = component
        self.expected_path = expected_path


class DecryptException(Exception):
    pass


class JobNotSerializable(TypeError):
    pass
