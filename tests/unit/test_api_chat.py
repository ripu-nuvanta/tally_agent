"""Tests for POST /api/chat endpoint."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.chat import router, _get_optional_db
from backend.api.dependencies import get_client, get_current_user, get_session_store
from backend.agents.context import SessionStore, SessionContext


@pytest.fixture(autouse=True)
def force_legacy_mode(monkeypatch):
    """Ensure chat tests run in legacy mode regardless of .env."""
    monkeypatch.setattr("backend.config.settings.DATABASE_URL", None)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    # Override auth + db dependencies for legacy-mode behavior
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    app.dependency_overrides[_get_optional_db] = lambda: None
    return app


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_session_store():
    store = SessionStore(ttl_minutes=60)
    return store


def test_chat_greeting(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "greeting",
        "message": "Hello! I'm your TallyPrime assistant.",
        "data": None,
        "chart": None,
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Hello! I'm your TallyPrime assistant."
    assert "session_id" in body


def test_chat_with_data(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "simple_lookup",
        "message": "Here is your trial balance.",
        "data": {"rows": [{"account": "Cash", "balance": 10000}]},
        "chart": None,
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Show trial balance"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] is not None


def test_chat_with_chart(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "comparison",
        "message": "Here is the comparison.",
        "data": {"rows": []},
        "chart": {"chart_type": "bar", "title": "Sales", "data": [{"x": "Q1", "y": 100}], "config": None},
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Compare Q1 vs Q2 sales"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["chart"]["chart_type"] == "bar"


def test_chat_preserves_session_id(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "greeting",
        "message": "Hi",
        "data": None,
        "chart": None,
        "session_id": "existing-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={
                "message": "Hello",
                "session_id": "existing-session",
            })

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "existing-session"


def test_chat_empty_message_rejected(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    with TestClient(app) as tc:
        resp = tc.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
