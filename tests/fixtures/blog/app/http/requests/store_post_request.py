from pydantic import Field

from fastogram.http import FormRequest


class StorePostRequest(FormRequest):
    title: str = Field(min_length=3, max_length=255)
