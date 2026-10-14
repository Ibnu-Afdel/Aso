"""Boot API (T-06): `Application.configure(base_path=__file__)...create()`."""

from fastogram.foundation.application import (
    Application,
    ApplicationBuilder,
    app,
    current_application,
    environment,
)
from fastogram.foundation.exceptions_config import ExceptionsConfig
from fastogram.foundation.middleware_config import MiddlewareConfig
from fastogram.foundation.paths import (
    app_path,
    base_path,
    config_path,
    database_path,
    public_path,
    resource_path,
    storage_path,
)

__all__ = [
    "Application",
    "ApplicationBuilder",
    "ExceptionsConfig",
    "MiddlewareConfig",
    "app",
    "app_path",
    "base_path",
    "config_path",
    "current_application",
    "database_path",
    "environment",
    "public_path",
    "resource_path",
    "storage_path",
]
