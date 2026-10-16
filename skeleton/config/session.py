"""Session configuration (T-18)."""

from aso.config import env
from aso.support import slug

driver = env("SESSION_DRIVER", "database")  # database | cookie | array (redis: later)
lifetime = int(env("SESSION_LIFETIME", 120))  # minutes of inactivity
expire_on_close = env("SESSION_EXPIRE_ON_CLOSE", False)
table = env("SESSION_TABLE", "sessions")
lottery = (2, 100)  # chance per request to prune expired rows

cookie = env("SESSION_COOKIE", slug(env("APP_NAME", "aso")) + "-session")
path = env("SESSION_PATH", "/")
domain = env("SESSION_DOMAIN", None)
secure = env("SESSION_SECURE_COOKIE", None)  # None = Secure when APP_URL is https
http_only = env("SESSION_HTTP_ONLY", True)
same_site = env("SESSION_SAME_SITE", "lax")

dont_flash = ["password", "password_confirmation", "current_password"]
