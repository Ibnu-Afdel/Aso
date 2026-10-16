"""Application configuration (T-03). Read anywhere with `config("app.<key>")`."""

from aso.config import env

name = env("APP_NAME", "Aso")
environment = env("APP_ENV", "production")
debug = env("APP_DEBUG", False)
url = env("APP_URL", "http://localhost:8000")
key = env("APP_KEY", "")
timezone = env("APP_TIMEZONE", "UTC")
locale = env("APP_LOCALE", "en")
faker_locale = env("APP_FAKER_LOCALE", "en_US")
