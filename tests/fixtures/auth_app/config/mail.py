from aso.config import env

# `array` (not the `log` guide default) so tests can read delivered messages back with
# `aso.mail.drivers.array_messages()`.
default: str = env("MAIL_MAILER", "array")

mailers: dict[str, dict] = {
    "array": {"transport": "array"},
}

from_address: dict[str, str] = {
    "address": env("MAIL_FROM_ADDRESS", "hello@example.com"),
    "name": env("MAIL_FROM_NAME", "AuthApp"),
}
