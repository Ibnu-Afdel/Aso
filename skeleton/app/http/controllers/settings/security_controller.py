"""Password settings (T-38, settings/security -- see `routes/settings.py` for why this page is
named `settings/security` rather than `settings/password`).
"""

from aso.http import Controller, redirect
from aso.inertia import inertia

from app.actions.auth.password_validation_rules import PasswordValidationRules
from app.http.requests.settings.password_update_request import PasswordUpdateRequest


class SecurityController(Controller):
    async def edit(self):
        return inertia("settings/security", {"passwordRules": PasswordValidationRules().description()})

    async def update(self, form: PasswordUpdateRequest):
        user = form.user()
        user.password = form.password  # the `Hashed` column hashes it on assignment (T-31, T-40)
        await user.save()
        return redirect().back().with_flash("status", "password-updated")
