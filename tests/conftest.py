"""Shared pytest fixtures for FastGram tests."""

import importlib

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture
def test_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """FastAPI test client. Sets BOT_ENABLED=false so no token required."""
    monkeypatch.setenv("BOT_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()
    from app import main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)
