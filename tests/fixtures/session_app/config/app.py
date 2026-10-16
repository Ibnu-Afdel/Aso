from aso.config import env

name = env("APP_NAME", "Session App")
environment = env("APP_ENV", "local")
debug = env("APP_DEBUG", False)
url = env("APP_URL", "http://testserver")
key = env("APP_KEY", "base64:dGVzdGluZy1rZXktdGVzdGluZy1rZXktMzJieXQ9MTI=")
