from aso.config import env

driver = env("SESSION_DRIVER", "array")
lifetime = int(env("SESSION_LIFETIME", 120))
expire_on_close = env("SESSION_EXPIRE_ON_CLOSE", False)
table = env("SESSION_TABLE", "sessions")
cookie = env("SESSION_COOKIE", "fg-session")
path = env("SESSION_PATH", "/")
domain = env("SESSION_DOMAIN", None)
secure = env("SESSION_SECURE_COOKIE", None)
http_only = env("SESSION_HTTP_ONLY", True)
same_site = env("SESSION_SAME_SITE", "lax")
