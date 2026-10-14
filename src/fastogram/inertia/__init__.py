"""Inertia.js v3 server protocol (T-16, T-17, D-002)."""

from fastogram.exceptions.types import PageNotFound
from fastogram.inertia.history import clear_history
from fastogram.inertia.middleware import InertiaMiddleware
from fastogram.inertia.property import PropertyContext, ProvidesInertiaProperty
from fastogram.inertia.props import always, deep_merge, defer, merge, once, optional, scroll
from fastogram.inertia.response import InertiaResponse, inertia, location
from fastogram.inertia.shared import share

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
