"""Inertia.js v3 server protocol (T-16, T-17, D-002)."""

from fastogram.exceptions.types import PageNotFound
from fastogram.inertia.middleware import InertiaMiddleware
from fastogram.inertia.response import InertiaResponse, defer, inertia

__all__ = ["InertiaMiddleware", "InertiaResponse", "PageNotFound", "defer", "inertia"]
