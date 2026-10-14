from fastogram.database import Mapped, Model, mapped_column
from sqlalchemy import String


class Post(Model):
    title: Mapped[str] = mapped_column(String(255))
