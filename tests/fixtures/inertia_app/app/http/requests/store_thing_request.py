from pydantic import Field

from fastogram.http import FormRequest


class StoreThingRequest(FormRequest):
    title: str = Field(min_length=3, max_length=255)
