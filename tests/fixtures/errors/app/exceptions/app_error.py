"""Used to test `render()` callback MRO ordering: `SpecificError` is a subclass of `AppError`."""

from __future__ import annotations


class AppError(Exception):
    pass


class SpecificError(AppError):
    pass
