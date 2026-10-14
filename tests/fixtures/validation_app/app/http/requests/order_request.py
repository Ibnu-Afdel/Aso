from pydantic import BaseModel, Field

from fastogram.validation import FormRequest


class OrderLine(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)


class StoreOrderRequest(FormRequest):
    lines: list[OrderLine] = Field(min_length=1)
    note: str | None = None
