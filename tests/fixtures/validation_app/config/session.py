from fastogram.config import env

driver = env("SESSION_DRIVER", "array")
cookie = "validation-app-session"
