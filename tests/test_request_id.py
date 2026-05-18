import importlib

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.bootstrap.request_id_middleware import add_request_id_middleware
from app.core.config import get_settings


def _build_client() -> TestClient:
    get_settings.cache_clear()
    from app import main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_request_id_header_exists(monkeypatch) -> None:
    monkeypatch.setenv("BOT_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = _build_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


def test_request_id_unique_per_request(monkeypatch) -> None:
    monkeypatch.setenv("BOT_ENABLED", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    client = _build_client()
    first = client.get("/healthz")
    second = client.get("/healthz")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_request_id_passthrough_header_and_state() -> None:
    app = FastAPI()
    add_request_id_middleware(app)

    @app.get("/probe")
    async def probe(request: Request):
        return {"request_id": request.state.request_id}

    client = TestClient(app)
    response = client.get("/probe", headers={"X-Request-ID": "my-id"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "my-id"
    assert response.headers["X-Request-ID"] == "my-id"
