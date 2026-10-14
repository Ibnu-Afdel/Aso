from fastogram.config import env

driver = env("SESSION_DRIVER", "array")
cookie = "inertia-app-session"
