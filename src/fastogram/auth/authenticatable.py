"""`Authenticatable` and `MustVerifyEmail` mixins (T-38, T-39).

```python
class User(MustVerifyEmail, Authenticatable, Model):
    ...
```

Mix them in *before* `Model` so their defaults (like `__hidden__`) lose to anything the model
itself declares, matching normal Python MRO.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

__all__ = ["Authenticatable", "MustVerifyEmail"]


class Authenticatable:
    """Adds `can()`/`cannot()` (T-39) and hides `password`/`remember_token` by default."""

    __hidden__: tuple[str, ...] = ("password", "remember_token")

    async def can(self, ability: str, *args: Any) -> bool:
        from fastogram.auth.gate import Gate

        return await Gate.for_user(self).allows(ability, *args)

    async def cannot(self, ability: str, *args: Any) -> bool:
        return not await self.can(ability, *args)


class MustVerifyEmail:
    """Turns on email verification for a user model (T-38)."""

    def has_verified_email(self) -> bool:
        return getattr(self, "email_verified_at", None) is not None

    async def mark_email_as_verified(self) -> bool:
        self.email_verified_at = datetime.now(UTC)
        await self.save()  # type: ignore[attr-defined]
        return True

    async def send_email_verification_notification(self) -> None:
        from fastogram.auth.mail import VerifyEmailMail
        from fastogram.mail import Mail

        await Mail.to(self.email).send(VerifyEmailMail(self))  # type: ignore[attr-defined]
