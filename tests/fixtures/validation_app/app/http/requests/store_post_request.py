from datetime import date

from pydantic import Field

from aso.validation import FormRequest


class StorePostRequest(FormRequest):
    title: str = Field(min_length=3, max_length=255)
    body: str
    slug: str | None = None

    def prepare_for_validation(self) -> None:
        title = self.input("title") or ""
        self.merge({"slug": title.lower().replace(" ", "-")})


class SecurePostRequest(FormRequest):
    """`authorize()` always says no -> 403 (T-19/T-20)."""

    title: str

    async def authorize(self) -> bool:
        return False


class StoreInvoiceRequest(FormRequest):
    issued_on: date
    due_on: date

    async def after(self) -> None:
        if self.due_on < self.issued_on:
            self.add_error("due_on", "The due date must be after the issue date.")


class CustomMessagesRequest(FormRequest):
    title: str = Field(min_length=3, max_length=255)
    published_at: date | None = None

    def messages(self) -> dict[str, str]:
        return {
            "title.required": "Every post needs a title.",
            "title.min": "Titles need at least :min characters.",
        }

    def attributes(self) -> dict[str, str]:
        return {"published_at": "publish date"}
