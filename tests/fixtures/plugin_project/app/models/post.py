from __future__ import annotations

from sqlalchemy import String

from fastogram.database import Mapped, Model, mapped_column


class Post(Model):
    __fillable__ = ["title"]

    title: Mapped[str] = mapped_column(String(255))
