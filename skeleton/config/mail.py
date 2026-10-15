"""Mail configuration (T-41)."""

from fastogram.config import env

default: str = env("MAIL_MAILER", "log")

mailers: dict[str, dict] = {
    "smtp": {
        "transport": "smtp",
        "host": env("MAIL_HOST", "127.0.0.1"),
        "port": int(env("MAIL_PORT", 2525)),
        "username": env("MAIL_USERNAME", None),
        "password": env("MAIL_PASSWORD", None),
        "scheme": env("MAIL_SCHEME", None),
    },
    "log": {
        "transport": "log",
        "channel": env("MAIL_LOG_CHANNEL", None),
    },
    "array": {
        "transport": "array",
    },
}

from_address: dict[str, str] = {
    "address": env("MAIL_FROM_ADDRESS", "hello@example.com"),
    "name": env("MAIL_FROM_NAME", env("APP_NAME", "FastoGram")),
}
