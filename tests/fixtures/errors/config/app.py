from aso.config import env

name = env("APP_NAME", "ErrorsApp")
environment = env("APP_ENV", "testing")
debug = env("APP_DEBUG", False)
url = env("APP_URL", "http://testserver")
key = env("APP_KEY", "base64:nDaTO0gCjJzrpc80a+ea/8uI7TeNmQdaW7N0FISGVjI=")
