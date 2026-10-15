from fastogram.config import env

default = env("DB_CONNECTION", "sqlite")
connections = {
    "sqlite": {"driver": "sqlite", "url": env("DB_URL"), "database": env("DB_DATABASE", ":memory:")},
}
