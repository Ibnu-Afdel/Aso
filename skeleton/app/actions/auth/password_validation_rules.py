"""The password rules shared by registration and password reset (T-38, Fortify's
`PasswordValidationRules` trait).

`rule()` is passed to `Password.defaults()` via `config/auth.py`; `description()` builds the
`passwordRules` help text the Laravel React kit's `register`/`reset-password`/`settings/security`
pages display under the password field.
"""

from aso.config import config
from aso.validation import Password


class PasswordValidationRules:
    def rule(self) -> Password:
        return Password.defaults()

    def description(self) -> str:
        rules = config("auth.password_rules", {})
        parts = [f"at least {rules.get('min', 8)} characters"]
        if rules.get("letters"):
            parts.append("letters")
        if rules.get("mixed_case"):
            parts.append("upper and lowercase letters")
        if rules.get("numbers"):
            parts.append("at least one number")
        if rules.get("symbols"):
            parts.append("at least one symbol")
        return "Must be " + ", ".join(parts) + "."
