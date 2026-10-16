"""Sets a user's new password (T-38, Fortify's `ResetUserPassword`).

`aso.auth.password_broker().reset()` already saves the new password and rotates
`remember_token` itself (T-38 "How it works"); this action exists so your own reset flow -- or a
custom `NewPasswordController` -- can reuse the same "how do we set a password" logic instead of
duplicating it, and so you have one obvious place to extend it (e.g. logging, notifying admins).
"""

from app.models.user import User


class ResetUserPassword:
    async def reset(self, user: User, password: str) -> None:
        user.password = password  # the `Hashed` column hashes it on assignment (T-31, T-40)
        await user.save()
