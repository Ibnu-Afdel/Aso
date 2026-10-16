"""Inertia.js v3 server protocol (T-16, T-17, D-002)."""

from aso.exceptions.types import PageNotFound
from aso.inertia.history import clear_history
from aso.inertia.middleware import InertiaMiddleware
from aso.inertia.property import PropertyContext, ProvidesInertiaProperty
from aso.inertia.props import always, deep_merge, defer, merge, once, optional, scroll
from aso.inertia.response import InertiaResponse, inertia, location
from aso.inertia.shared import share

__all__ = [
    "InertiaMiddleware",
    "InertiaResponse",
    "PageNotFound",
    "PropertyContext",
    "ProvidesInertiaProperty",
    "always",
    "clear_history",
    "deep_merge",
    "defer",
    "inertia",
    "location",
    "merge",
    "once",
    "optional",
    "scroll",
    "share",
]
