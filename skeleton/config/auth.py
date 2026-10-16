"""Authentication configuration (T-38). Guards, providers, password broker, feature flags."""

from aso.config import env
from aso.validation import Password

defaults = {"guard": "web", "passwords": "users"}

guards = {
    "web": {"driver": "session", "provider": "users"},
}

providers = {
    "users": {"driver": "model", "model": "app.models.user.User"},
}

passwords = {
    "users": {
        "provider": "users",
        "table": "password_reset_tokens",
        "expire": 60,  # minutes a reset link is valid
        "throttle": 60,  # seconds before another link can be requested
    },
}

password_timeout = int(env("AUTH_PASSWORD_TIMEOUT", 10800))  # seconds a password confirmation lasts (3h)

# Remove a name to switch that auth flow off. Its routes stop being registered (routes/auth.py)
# and the kit's pages hide the matching links.
features = ["registration", "reset_passwords", "email_verification"]

# Plain, descriptive settings (used by `app/actions/auth/password_validation_rules.py` to build
# the `passwordRules` help text shown on the register/reset-password pages).
password_rules = {"min": 8, "letters": False, "mixed_case": False, "numbers": False, "symbols": False}

# `Password.defaults()` (aso.validation) reads `config("auth.password_defaults")`. It must
# be a concrete `Password` instance here: the config loader strips every function/lambda from a
# config module before caching it (`aso.config._module_values`), so the callable form the
# docstring also documents can never actually be read back from a config file -- see the build
# report. Keep this in sync with `password_rules` above.
password_defaults = Password().min(password_rules["min"])
if password_rules["letters"]:
    password_defaults = password_defaults.letters()
if password_rules["mixed_case"]:
    password_defaults = password_defaults.mixed_case()
if password_rules["numbers"]:
    password_defaults = password_defaults.numbers()
if password_rules["symbols"]:
    password_defaults = password_defaults.symbols()

remember_lifetime = 60 * 24 * 400  # minutes (~400 days), like Laravel's recaller cookie
