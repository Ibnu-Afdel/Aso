from sqlalchemy import String, Text

from fastogram.database import Mapped, Model, mapped_column


class Post(Model):
    __fillable__ = ["title", "body"]

    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
