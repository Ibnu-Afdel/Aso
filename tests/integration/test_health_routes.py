"""Integration tests for health endpoints."""

import pytest


def test_liveness_ok(test_client):
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_ok_when_db_reachable(test_client, monkeypatch):
    from unittest.mock import AsyncMock, patch

    from app.services.health import HealthAppService

    healthy = HealthAppService.__new__(HealthAppService)
    healthy.readiness = AsyncMock(return_value={"status": "ok", "database": "ok"})

    with patch("app.bootstrap.container._health_app_service", healthy):
        response = test_client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_readyz_503_when_db_unreachable(test_client):
    from unittest.mock import AsyncMock, patch

    from app.services.health import HealthAppService

    degraded = HealthAppService.__new__(HealthAppService)
    degraded.readiness = AsyncMock(
        return_value={"status": "degraded", "database": "unreachable"}
    )

    with patch("app.bootstrap.container._health_app_service", degraded):
        response = test_client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
