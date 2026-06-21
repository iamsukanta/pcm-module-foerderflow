"""Smoke test: app boots and /health responds. No DB needed."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_served() -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"]
