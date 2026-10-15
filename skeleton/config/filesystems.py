"""Filesystem disks (T-43). `storage(disk)` reads this to resolve the default disk."""

from fastogram.config import env
from fastogram.foundation import base_path

default = env("FILESYSTEM_DISK", "local")

disks = {
    "local": {
        "driver": "local",
        "root": str(base_path("storage", "app")),
    },
    "public": {
        "driver": "local",
        "root": str(base_path("storage", "app", "public")),
        "url": env("APP_URL", "http://localhost:8000").rstrip("/") + "/storage",
    },
}
