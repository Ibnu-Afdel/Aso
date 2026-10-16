"""The default `users` table model (T-31, T-38)."""

from datetime import datetime

from sqlalchemy import String

from aso.auth import Authenticatable, MustVerifyEmail
from aso.database import Hashed, Mapped, Model, mapped_column


class User(MustVerifyEmail, Authenticatable, Model):
    __fillable__ = ["name", "email", "password"]
    __hidden__ = ["password", "remember_token"]

    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    password: Mapped[str] = mapped_column(Hashed(String(255)))
    remember_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
