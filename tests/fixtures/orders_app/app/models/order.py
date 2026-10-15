from sqlalchemy import String

from fastogram.database import Mapped, Model, mapped_column


class Order(Model):
    status: Mapped[str] = mapped_column(String(50))
    customer_email: Mapped[str] = mapped_column(String(255))
