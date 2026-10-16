"""Database configuration (T-30). SQLite by default (D-019); switch by changing `.env`."""

from aso.config import env
from aso.foundation import database_path

default = env("DB_CONNECTION", "sqlite")

connections = {
    "sqlite": {
        "driver": "sqlite",
        "database": env("DB_DATABASE", str(database_path("database.sqlite"))),
    },
    "pgsql": {
        "driver": "pgsql",
        "host": env("DB_HOST", "127.0.0.1"),
        "port": int(env("DB_PORT", 5432)),
        "database": env("DB_DATABASE", "aso"),
        "username": env("DB_USERNAME", "postgres"),
        "password": env("DB_PASSWORD", ""),
        "sslmode": env("DB_SSLMODE", None),
    },
    "mysql": {
        "driver": "mysql",
        "host": env("DB_HOST", "127.0.0.1"),
        "port": int(env("DB_PORT", 3306)),
        "database": env("DB_DATABASE", "aso"),
        "username": env("DB_USERNAME", "root"),
        "password": env("DB_PASSWORD", ""),
    },
}

pool = {"size": int(env("DB_POOL_SIZE", 5)), "max_overflow": int(env("DB_POOL_MAX_OVERFLOW", 10))}

log_queries = env("DB_LOG_QUERIES", False)
