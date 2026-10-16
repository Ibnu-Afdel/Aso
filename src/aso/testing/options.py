"""`_PendingOptions`: the fluent state a `TestClient` copy carries into its next request (T-56
"Fluent configuration")."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

__all__ = ["PendingOptions"]


@dataclass(frozen=True)
class PendingOptions:
    headers: dict[str, str] = field(default_factory=dict)
    extra_cookies: dict[str, str] = field(default_factory=dict)
    session_patch: dict[str, Any] = field(default_factory=dict)
    acting_as_user: Any = None
    referer: str | None = None
    inertia: bool = False
    inertia_version: str | None = None
    without_middleware: tuple[str, ...] | None = None
    force_csrf: bool = False
    raise_exceptions: bool = False
    follow: bool = False

    def copy(self, **overrides: Any) -> PendingOptions:
        return replace(self, **overrides)
