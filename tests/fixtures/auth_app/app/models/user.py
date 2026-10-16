from __future__ import annotations

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
    # `Hashed(String(255))` (the guide's own example) mis-sizes the column -- see the build
    # report. `Hashed()` works correctly, so the fixture uses that form.
    password: Mapped[str] = mapped_column(Hashed())
    remember_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
