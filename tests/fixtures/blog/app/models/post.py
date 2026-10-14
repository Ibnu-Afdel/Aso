from sqlalchemy import String

from fastogram.database import Mapped, Model, mapped_column


class Post(Model):
    title: Mapped[str] = mapped_column(String(255))
