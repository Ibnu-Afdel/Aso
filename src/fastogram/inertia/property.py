"""`ProvidesInertiaProperty` and `PropertyContext` (T-16 "Custom prop objects")."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PropertyContext:
    """Passed to `to_inertia_property()`: `key` (this prop's name), `props` (all declared props,
    before resolution) and `request`."""

    key: str
    props: dict[str, Any]
    request: Any


@runtime_checkable
class ProvidesInertiaProperty(Protocol):
    """A class can decide how it appears as a prop by implementing this method (sync or async)."""

    def to_inertia_property(self, context: PropertyContext) -> Any: ...
