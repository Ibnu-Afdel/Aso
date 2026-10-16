from datetime import datetime

from sqlalchemy import String

from aso.database import Hashed, Mapped, Model, has_many, mapped_column


class User(Model):
    __fillable__ = ["name", "email", "password"]

    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(Hashed(String(255)))
    email_verified_at: Mapped[datetime | None]

    posts: Mapped[list["Post"]] = has_many("Post")  # noqa: F821
