from sqlalchemy import Integer, String

from fastogram.database import Mapped, Model, mapped_column


class Comment(Model):
    """Table `comments`. `post_id` is the FK the scoped-binding step (T-10) looks for when a
    nested resource's child is loaded "through the parent" (`/posts/{post}/comments/{comment}`)."""

    body: Mapped[str] = mapped_column(String(255))
    post_id: Mapped[int] = mapped_column(Integer)
