"""Mail (T-41, D-028): `Mailable`, `Mail.to(...).send()` / `.queue()`.

```python
from fastogram.mail import Mail, Mailable, Envelope, Content

class WelcomeMail(Mailable):
    def __init__(self, user) -> None:
        self.user = user

    def envelope(self) -> Envelope:
        return Envelope(subject="Welcome!")

    def content(self) -> Content:
        return Content(view="mail/welcome.html", with_={"user": self.user})

await Mail.to(user.email).send(WelcomeMail(user))
await Mail.to(user.email).queue(WelcomeMail(user))
```

Drivers `log` (default locally), `array` (tests), `smtp` (`aiosmtplib`). `Mail.fake()` plus
class-level assertions for tests. `config/mail.py` defaults when missing (`drivers.py`).
"""

from __future__ import annotations

from fastogram.mail.mailable import Attachment, Content, Envelope, Mailable
from fastogram.mail.manager import Mail, SentMail, reset_mail
from fastogram.mail.queued_mail import SendQueuedMail

__all__ = [
    "Attachment",
    "Content",
    "Envelope",
    "Mail",
    "Mailable",
    "SendQueuedMail",
    "SentMail",
    "reset_mail",
]
