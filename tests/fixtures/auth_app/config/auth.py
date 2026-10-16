from aso.config import env

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
        "expire": 60,  # minutes
        "throttle": 60,  # seconds
    },
}

password_timeout = int(env("AUTH_PASSWORD_TIMEOUT", 10800))

features = ["registration", "reset_passwords", "email_verification"]

remember_lifetime = 60 * 24 * 400
