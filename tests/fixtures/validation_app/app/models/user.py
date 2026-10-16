from sqlalchemy import String

from aso.database import Mapped, Model, mapped_column


class User(Model):
    """Table `users`, used by the `Unique`/`Exists` rule tests."""

    email: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255), default="")
