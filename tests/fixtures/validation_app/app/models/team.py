from sqlalchemy import String

from fastogram.database import Mapped, Model, mapped_column


class Team(Model):
    """Table `teams`, used by the `Exists` rule test."""

    name: Mapped[str] = mapped_column(String(255), default="Team")
