from __future__ import annotations

from fastogram.database import Model, mapped_column
from fastogram.http import Request  # noqa: F401


class Post(Model):
    __fillable__ = ["title", "body"]

    title: str = mapped_column()
