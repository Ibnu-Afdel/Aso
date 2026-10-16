from sqlalchemy import String

from aso.database import Mapped, Model, mapped_column


class Post(Model):
    title: Mapped[str] = mapped_column(String(255))
