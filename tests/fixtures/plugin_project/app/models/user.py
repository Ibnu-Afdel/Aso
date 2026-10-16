from __future__ import annotations

from sqlalchemy import String

from aso.auth import Authenticatable
from aso.database import Hashed, Mapped, Model, mapped_column


class User(Authenticatable, Model):
    __fillable__ = ["name", "email", "password"]
    __hidden__ = ["password"]

    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(Hashed())
