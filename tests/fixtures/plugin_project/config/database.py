from fastogram.config import env

default = env("DB_CONNECTION", "sqlite")
connections = {
    "sqlite": {"driver": "sqlite", "database": env("DB_DATABASE", ":memory:")},
}
