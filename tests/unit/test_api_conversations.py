"""Unit tests for conversation CRUD API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.conversations import router
from backend.api.dependencies import get_current_user
from backend.db.engine import get_db


USER_ID = str(uuid.uuid4())
WORKSPACE_ID = str(uuid.uuid4())


def _make_mock_workspace(ws_id=WORKSPACE_ID, user_id=USER_ID):
    ws = MagicMock()
    ws.id = ws_id
    ws.user_id = user_id
    ws.is_deleted = False
    return ws


def _make_mock_conversation(conv_id=None, workspace_id=WORKSPACE_ID, user_id=USER_ID,
                            title=None, tag=None, messages=None):
    conv = MagicMock()
    conv.id = conv_id or uuid.uuid4()
    conv.workspace_id = workspace_id
    conv.user_id = user_id
    conv.title = title
    conv.tag = tag
    conv.is_deleted = False
    conv.messages = messages or []
    conv.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    conv.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return conv


def _make_mock_message(role="user", content="hello"):
    msg = MagicMock()
    msg.id = uuid.uuid4()
    msg.role = role
    msg.content = content
    msg.data = None
    msg.chart = None
    msg.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return msg


def _make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: USER_ID
    return app


def _setup_db_with_workspace(mock_db, workspace=None):
    """Configure the mock_db so the first execute() returns the workspace,
    and subsequent calls can be configured separately."""
    ws = workspace or _make_mock_workspace()
    ws_result = MagicMock()
    ws_result.scalar_one_or_none.return_value = ws
    return ws_result


class TestListConversations:
    def test_list_conversations_empty(self, app):
        mock_db = _make_mock_db()
        # First call: workspace access check, second: conversation list
        ws_result = _setup_db_with_workspace(mock_db)
        conv_result = MagicMock()
        conv_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [ws_result, conv_result]
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get(f"/api/workspaces/{WORKSPACE_ID}/conversations")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_conversations_returns_items(self, app):
        conv1 = _make_mock_conversation(title="Chat 1")
        conv2 = _make_mock_conversation(title="Chat 2")

        mock_db = _make_mock_db()
        ws_result = _setup_db_with_workspace(mock_db)
        conv_result = MagicMock()
        conv_result.scalars.return_value.all.return_value = [conv1, conv2]
        mock_db.execute.side_effect = [ws_result, conv_result]
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get(f"/api/workspaces/{WORKSPACE_ID}/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "Chat 1"

    def test_list_conversations_workspace_not_found_404(self, app):
        mock_db = _make_mock_db()
        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = ws_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get(f"/api/workspaces/{uuid.uuid4()}/conversations")

        assert resp.status_code == 404


class TestCreateConversation:
    def test_create_conversation_success(self, app):
        conv_id = uuid.uuid4()
        mock_db = _make_mock_db()
        ws_result = _setup_db_with_workspace(mock_db)
        mock_db.execute.return_value = ws_result

        async def fake_refresh(conv):
            conv.id = conv_id
            conv.title = "New Chat"
            conv.tag = None
            conv.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            conv.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.post(
                f"/api/workspaces/{WORKSPACE_ID}/conversations",
                json={"title": "New Chat"},
            )

        assert resp.status_code == 201
        assert resp.json()["title"] == "New Chat"


class TestGetConversation:
    def test_get_conversation_with_messages(self, app):
        msg1 = _make_mock_message(role="user", content="hello")
        msg2 = _make_mock_message(role="assistant", content="Hi there!")
        conv = _make_mock_conversation(title="Detail Chat", messages=[msg1, msg2])

        mock_db = _make_mock_db()
        ws_result = _setup_db_with_workspace(mock_db)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv
        mock_db.execute.side_effect = [ws_result, conv_result]
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get(
                f"/api/workspaces/{WORKSPACE_ID}/conversations/{conv.id}"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["content"] == "Hi there!"

    def test_get_conversation_not_found_404(self, app):
        mock_db = _make_mock_db()
        ws_result = _setup_db_with_workspace(mock_db)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [ws_result, conv_result]
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get(
                f"/api/workspaces/{WORKSPACE_ID}/conversations/{uuid.uuid4()}"
            )

        assert resp.status_code == 404


class TestDeleteConversation:
    def test_delete_conversation_success(self, app):
        conv = _make_mock_conversation()
        mock_db = _make_mock_db()
        ws_result = _setup_db_with_workspace(mock_db)
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv
        mock_db.execute.side_effect = [ws_result, conv_result]
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.delete(
                f"/api/workspaces/{WORKSPACE_ID}/conversations/{conv.id}"
            )

        assert resp.status_code == 204
        assert conv.is_deleted is True
