from __future__ import annotations

from sqlalchemy import Integer, String

from aso.database import Mapped, Model, mapped_column


class Post(Model):
    __fillable__ = ["title", "body", "user_id"]

    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(1000), default="")
    user_id: Mapped[int] = mapped_column(Integer)
