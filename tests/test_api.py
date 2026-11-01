"""HTTP contract tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from kipu_pay.main import create_app
from kipu_pay.core.config import Settings


def _client(settings: Settings | None = None) -> TestClient:
    app = create_app(settings or Settings())
    return TestClient(app)


def test_health_200():
    client = _client()
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_body_structure():
    client = _client()
    response = client.get("/v1/health")
    data = response.json()
    assert set(data.keys()) == {"status", "team", "version", "models"}
    assert data["status"] == "ok"
    assert isinstance(data["team"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["models"], list)


def test_health_team_matches_settings():
    settings = Settings(team_name="frontier-team", app_version="0.5.0")
    client = _client(settings)
    response = client.get("/v1/health")
    data = response.json()
    assert data["team"] == "frontier-team"
    assert data["version"] == "0.5.0"
    assert data["models"] == []


def test_health_no_auth_required():
    client = _client()
    response = client.get("/v1/health", headers={})
    assert response.status_code == 200


def test_health_no_secrets_in_response():
    client = _client()
    response = client.get("/v1/health")
    body = response.text.lower()
    forbidden = ["token", "password", "secret", "database_url", "postgres"]
    for term in forbidden:
        assert term not in body, f"Potential leak: '{term}' in health response"


def test_health_returns_request_id_header():
    client = _client()
    response = client.get("/v1/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_health_propagates_request_id():
    client = _client()
    response = client.get("/v1/health", headers={"x-request-id": "custom-id-123"})
    assert response.headers["x-request-id"] == "custom-id-123"


def test_health_repeated_requests_consistent():
    client = _client()
    r1 = client.get("/v1/health")
    r2 = client.get("/v1/health")
    assert r1.json() == r2.json()


def test_unknown_endpoint_404():
    client = _client()
    response = client.get("/v1/nonexistent")
    assert response.status_code == 404
    body = response.json()
    # FastAPI default 404 is safe; ensure no stack trace leak
    assert "traceback" not in str(body).lower()
    assert "stack" not in str(body).lower()


def test_health_db_not_required():
    """Health is liveness; DB is not contacted."""
    settings = Settings()  # no DB URL configured
    client = _client(settings)
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_alias_both_paths_200():
    """Regression: FRONTIER validator calls GET /health at root; /v1/health must also work."""
    client = _client()
    r_root = client.get("/health")
    r_v1 = client.get("/v1/health")
    assert r_root.status_code == 200
    assert r_v1.status_code == 200
    assert r_root.json() == r_v1.json()
    body = r_root.json()
    assert body["status"] == "ok"
    assert set(body.keys()) == {"status", "team", "version", "models"}
