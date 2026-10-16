from __future__ import annotations

from aso.database import Model, mapped_column
from aso.http import Request  # noqa: F401


class Post(Model):
    __fillable__ = ["title", "body"]

    title: str = mapped_column()
