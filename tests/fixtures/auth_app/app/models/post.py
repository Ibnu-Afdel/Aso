from __future__ import annotations

from sqlalchemy import Integer, String

from aso.database import Mapped, Model, mapped_column


class Post(Model):
    title: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(Integer)
