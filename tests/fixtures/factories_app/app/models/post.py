from sqlalchemy import ForeignKey, String, Text

from fastogram.database import Mapped, Model, belongs_to, mapped_column


class Post(Model):
    __fillable__ = ["title", "body"]

    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user: Mapped["User"] = belongs_to("User")  # noqa: F821
