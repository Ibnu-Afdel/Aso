"""Cache configuration (T-44). `cache()` reads this to resolve the default store."""

from aso.config import env
from aso.foundation import storage_path

default = env("CACHE_STORE", "file")

stores = {
    "memory": {"driver": "memory"},
    "file": {"driver": "file", "path": str(storage_path("framework", "cache"))},
    "redis": {"driver": "redis", "connection": env("REDIS_URL", "redis://127.0.0.1:6379/1")},
}

prefix = env("CACHE_PREFIX", "aso_cache_")
