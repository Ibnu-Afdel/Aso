from fastogram.config import env

# `array` here (not the `log` guide default) so the real-stack test can read delivered messages
# back with `fastogram.mail.drivers.array_messages()` instead of parsing log output.
default: str = env("MAIL_MAILER", "array")

mailers: dict[str, dict] = {
    "array": {"transport": "array"},
}

from_address: dict[str, str] = {
    "address": env("MAIL_FROM_ADDRESS", "hello@example.com"),
    "name": env("MAIL_FROM_NAME", "OrdersApp"),
}
