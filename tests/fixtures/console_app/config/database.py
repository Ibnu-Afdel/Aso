from fastogram.config import env

default = env("DB_CONNECTION", "sqlite")
connections = {
    "sqlite": {"driver": "sqlite", "url": env("FIXTURE_DB_URL"), "database": env("DB_DATABASE", ":memory:")},
}
