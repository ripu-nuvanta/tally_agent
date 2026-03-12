"""Tests for GET /api/health endpoint."""

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.health import router
from backend.api.dependencies import get_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.base_url = "http://localhost:9000"
    client.mock_mode = False
    return client


def test_health_tally_connected(app, mock_client):
    mock_client.health_check.return_value = True
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["tally_connected"] is True
    assert "tally_url" in body


def test_health_tally_disconnected(app, mock_client):
    mock_client.health_check.return_value = False
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["tally_connected"] is False
