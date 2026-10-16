"""Logging configuration (T-22)."""

from aso.config import env
from aso.foundation import storage_path

default = env("LOG_CHANNEL", "stack")

level = env("LOG_LEVEL", "debug")

channels = {
    "stack": {"driver": "stack", "channels": ["single"]},
    "single": {"driver": "single", "path": str(storage_path("logs", "aso.log"))},
    "daily": {"driver": "daily", "path": str(storage_path("logs", "aso.log")), "days": 14},
    "stderr": {"driver": "stderr"},
}

# Keys whose values are replaced with "[redacted]" in structured log output.
redact = ["password", "password_confirmation", "current_password", "token", "secret"]
