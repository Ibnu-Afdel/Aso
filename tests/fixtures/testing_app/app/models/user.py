from __future__ import annotations

from sqlalchemy import String

from fastogram.auth import Authenticatable, MustVerifyEmail
from fastogram.database import Hashed, Mapped, Model, mapped_column


class User(MustVerifyEmail, Authenticatable, Model):
    __fillable__ = ["name", "email", "password"]
    __hidden__ = ["password", "remember_token"]

    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(Hashed())
    remember_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
