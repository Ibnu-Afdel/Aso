from pydantic import Field

from aso.http import FormRequest


class UpdatePostRequest(FormRequest):
    title: str = Field(min_length=3, max_length=255)
