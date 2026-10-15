"""`Mailable`, `Envelope`, `Content`, `Attachment` (T-41).

```python
class WelcomeMail(Mailable):
    def __init__(self, user: User) -> None:
        self.user = user

    def envelope(self) -> Envelope:
        return Envelope(subject=f"Welcome, {self.user.name}!")

    def content(self) -> Content:
        return Content(view="mail/welcome.html", with_={"user": self.user})
```
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Envelope:
    subject: str
    from_: str | tuple[str, str] | None = None
    reply_to: str | list[str] | None = None


@dataclass
class Content:
    view: str | None = None
    text: str | None = None
    with_: dict[str, Any] = field(default_factory=dict)


@dataclass
class Attachment:
    """Either `path` (read from disk when the mail is rendered) or raw `data`."""

    path: str | Path | None = None
    data: bytes | None = None
    name: str | None = None
    content_type: str | None = None

    @classmethod
    def from_path(cls, path: str | Path, *, name: str | None = None, content_type: str | None = None) -> Attachment:
        return cls(path=path, name=name or Path(path).name, content_type=content_type)

    @classmethod
    def from_data(cls, data: bytes, name: str, *, content_type: str | None = None) -> Attachment:
        return cls(data=data, name=name, content_type=content_type)

    def read(self) -> bytes:
        if self.data is not None:
            return self.data
        if self.path is not None:
            return Path(self.path).read_bytes()
        raise ValueError("Attachment has neither `path` nor `data`.")

    def resolved_name(self) -> str:
        if self.name:
            return self.name
        if self.path is not None:
            return Path(self.path).name
        return "attachment"

    def to_wire(self) -> dict[str, Any]:
        """A JSON-serialisable form, used for queued mail (D-028) and `array`/fake recording."""
        return {
            "name": self.resolved_name(),
            "content_type": self.content_type,
            "data_b64": base64.b64encode(self.read()).decode("ascii"),
        }


class Mailable:
    """Subclass, implement `envelope()` and `content()`; `attachments()` defaults to none."""

    def envelope(self) -> Envelope:
        raise NotImplementedError(f"{type(self).__name__} must implement envelope().")

    def content(self) -> Content:
        raise NotImplementedError(f"{type(self).__name__} must implement content().")

    def attachments(self) -> list[Attachment]:
        return []

    def render(self) -> str:
        """The rendered HTML body. Synchronous: a controller returning a `Mailable` gets this
        (already supported by `fastogram.http.encoding.to_response`)."""
        content = self.content()
        if content.view:
            from fastogram.mail.rendering import render_view

            return render_view(content.view, content.with_)
        return content.text or ""
