from sqlalchemy import String

from aso.database import Mapped, Model, mapped_column


class Post(Model):
    """Table `posts`. `slug` is used by the `{post:slug}` route-model-binding test (T-10)."""

    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
