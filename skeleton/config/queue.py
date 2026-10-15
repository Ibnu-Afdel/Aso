"""Queue configuration (T-42). `sync` runs jobs inline; switch to `redis` for a real worker."""

from fastogram.config import env

default = env("QUEUE_CONNECTION", "sync")

connections = {
    "sync": {"driver": "sync"},
    "redis": {
        "driver": "redis",
        "url": env("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "queue": env("REDIS_QUEUE", "default"),
    },
}
