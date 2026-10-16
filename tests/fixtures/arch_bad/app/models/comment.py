from __future__ import annotations

from aso.database import Model, mapped_column


class Comment(Model):
    body: str = mapped_column()
