"""Tests for POST /api/chat in DB mode."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.chat import router, _get_optional_db
from backend.api.dependencies import get_client, get_current_user, get_session_store
from backend.agents.context import SessionStore


USER_ID = str(uuid.uuid4())
WORKSPACE_ID = str(uuid.uuid4())
CONVERSATION_ID = str(uuid.uuid4())


def _make_mock_workspace(ws_id=None, user_id=USER_ID, name="Test Co",
                         agent_type="tally", config=None):
    ws = MagicMock()
    ws.id = ws_id or uuid.uuid4()
    ws.user_id = user_id
    ws.name = name
    ws.agent_type = agent_type
    ws.config = config or {}
    ws.is_deleted = False
    ws.title = None
    ws.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ws


def _make_mock_conversation(conv_id=None, workspace_id=WORKSPACE_ID, user_id=USER_ID):
    conv = MagicMock()
    conv.id = conv_id or uuid.uuid4()
    conv.workspace_id = workspace_id
    conv.user_id = user_id
    conv.is_deleted = False
    conv.title = None
    conv.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return conv


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_assistant_msg():
    msg = MagicMock()
    msg.id = uuid.uuid4()
    return msg


@pytest.fixture(autouse=True)
def force_db_mode(monkeypatch):
    """Force DB mode on for all tests in this module."""
    monkeypatch.setattr("backend.config.settings.DATABASE_URL",
                        "postgresql+asyncpg://user:pass@localhost/test")


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(router, prefix="/api")
    a.dependency_overrides[get_current_user] = lambda: USER_ID
    # get_session_store reads from app.state; override to avoid AttributeError
    a.dependency_overrides[get_session_store] = lambda: SessionStore(ttl_minutes=60)
    return a


@pytest.fixture
def mock_client():
    return AsyncMock()


# ---------------------------------------------------------------------------
# Test 1: chat requires auth in DB mode (no auth header → 401)
# ---------------------------------------------------------------------------

def test_chat_db_mode_requires_auth():
    """Without auth override, missing credentials should raise 401 in DB mode."""
    a = FastAPI()
    a.include_router(router, prefix="/api")
    # No dependency override for get_current_user — real dependency fires
    a.dependency_overrides[_get_optional_db] = lambda: None
    a.dependency_overrides[get_client] = lambda: AsyncMock()
    a.dependency_overrides[get_session_store] = lambda: SessionStore(ttl_minutes=60)

    with TestClient(a, raise_server_exceptions=False) as tc:
        resp = tc.post("/api/chat", json={
            "message": "Hello",
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
        })

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 2: chat requires workspace_id in DB mode (missing → 400)
# ---------------------------------------------------------------------------

def test_chat_db_mode_requires_workspace_id(app, mock_client):
    """Chat endpoint must reject requests with no workspace_id in DB mode."""
    mock_db = _make_mock_db()
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[_get_optional_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.post("/api/chat", json={
            "message": "Show sales",
            "conversation_id": CONVERSATION_ID,
            # workspace_id intentionally omitted
        })

    assert resp.status_code == 400
    assert "workspace_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 3: chat saves user + assistant messages to DB
# ---------------------------------------------------------------------------

def test_chat_db_mode_saves_messages(app, mock_client):
    """DB mode chat persists user message and assistant message via db.add."""
    workspace = _make_mock_workspace(ws_id=WORKSPACE_ID)
    conversation = _make_mock_conversation(
        conv_id=CONVERSATION_ID, workspace_id=WORKSPACE_ID
    )

    mock_db = _make_mock_db()

    # db.execute is called 3 times: load workspace, load conversation, load prior msgs
    ws_result = MagicMock()
    ws_result.scalar_one_or_none.return_value = workspace
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [ws_result, conv_result, msgs_result]

    agent_result = {
        "message": "Here is your data.",
        "data": None,
        "chart": None,
        "session_id": str(CONVERSATION_ID),
        "usage": [],
    }

    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[_get_optional_db] = lambda: mock_db

    with patch("backend.agents.registry.get_agent") as mock_get_agent:
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_instance.process_query = AsyncMock(return_value=agent_result)
        mock_agent_class.return_value = mock_agent_instance
        mock_get_agent.return_value = mock_agent_class

        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={
                "message": "Show sales",
                "workspace_id": str(WORKSPACE_ID),
                "conversation_id": str(CONVERSATION_ID),
            })

    assert resp.status_code == 200
    # db.add should have been called at least twice: user message + assistant message
    assert mock_db.add.call_count >= 2
    assert mock_db.commit.called


# ---------------------------------------------------------------------------
# Test 4: chat logs usage when agent returns usage data
# ---------------------------------------------------------------------------

def test_chat_db_mode_logs_usage(app, mock_client):
    """Usage log entry is added to DB when agent returns usage tokens."""
    workspace = _make_mock_workspace(ws_id=WORKSPACE_ID)
    conversation = _make_mock_conversation(
        conv_id=CONVERSATION_ID, workspace_id=WORKSPACE_ID
    )

    mock_db = _make_mock_db()
    ws_result = MagicMock()
    ws_result.scalar_one_or_none.return_value = workspace
    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [ws_result, conv_result, msgs_result]

    agent_result = {
        "message": "Trial balance.",
        "data": None,
        "chart": None,
        "session_id": str(CONVERSATION_ID),
        "usage": [
            {"model": "claude-sonnet-4-6", "input_tokens": 500, "output_tokens": 200},
        ],
    }

    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[_get_optional_db] = lambda: mock_db

    with patch("backend.agents.registry.get_agent") as mock_get_agent:
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_agent_instance.process_query = AsyncMock(return_value=agent_result)
        mock_agent_class.return_value = mock_agent_instance
        mock_get_agent.return_value = mock_agent_class

        with patch("backend.utils.pricing.compute_cost", return_value=0.001):
            with TestClient(app) as tc:
                resp = tc.post("/api/chat", json={
                    "message": "Show trial balance",
                    "workspace_id": str(WORKSPACE_ID),
                    "conversation_id": str(CONVERSATION_ID),
                })

    assert resp.status_code == 200
    # 3 add calls: user msg + assistant msg + usage log
    assert mock_db.add.call_count >= 3


# ---------------------------------------------------------------------------
# Test 5: workspace ownership check — other user's workspace returns 404
# ---------------------------------------------------------------------------

def test_chat_db_mode_workspace_ownership_check(app, mock_client):
    """If workspace belongs to a different user, return 404."""
    mock_db = _make_mock_db()

    # workspace lookup returns None (different user or deleted)
    ws_result = MagicMock()
    ws_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = ws_result

    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[_get_optional_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.post("/api/chat", json={
            "message": "Show sales",
            "workspace_id": str(uuid.uuid4()),  # any workspace id
            "conversation_id": str(CONVERSATION_ID),
        })

    assert resp.status_code == 404
    assert "Workspace not found" in resp.json()["detail"]
