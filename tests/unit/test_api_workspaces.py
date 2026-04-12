"""Unit tests for workspace CRUD API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.workspaces import router
from backend.api.dependencies import get_current_user
from backend.db.engine import get_db


USER_ID = str(uuid.uuid4())


def _make_mock_workspace(ws_id=None, name="Test Co", user_id=USER_ID,
                         agent_type="tally", config=None, memory=None):
    ws = MagicMock()
    ws.id = ws_id or uuid.uuid4()
    ws.user_id = user_id
    ws.name = name
    ws.agent_type = agent_type
    ws.config = config or {}
    ws.memory = memory or {}
    ws.is_deleted = False
    ws.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ws.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ws


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


class TestListWorkspaces:
    def test_list_workspaces_empty(self, app):
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get("/api/workspaces")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_workspaces_returns_items(self, app):
        ws1 = _make_mock_workspace(name="Company A")
        ws2 = _make_mock_workspace(name="Company B")

        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ws1, ws2]
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.get("/api/workspaces")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Company A"
        assert data[1]["name"] == "Company B"


class TestCreateWorkspace:
    def test_create_workspace_success(self, app):
        ws_id = uuid.uuid4()
        mock_db = _make_mock_db()

        async def fake_refresh(ws):
            ws.id = ws_id
            ws.name = "New Co"
            ws.agent_type = "tally"
            ws.config = {}
            ws.memory = {}
            ws.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            ws.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.post("/api/workspaces", json={"name": "New Co"})

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Co"
        assert body["agent_type"] == "tally"

    def test_create_workspace_with_config(self, app):
        ws_id = uuid.uuid4()
        mock_db = _make_mock_db()

        async def fake_refresh(ws):
            ws.id = ws_id
            ws.name = "Configured Co"
            ws.agent_type = "tally"
            ws.config = {"tally_host": "192.168.1.5", "tally_port": 9000}
            ws.memory = {}
            ws.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            ws.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.post("/api/workspaces", json={
                "name": "Configured Co",
                "config": {"tally_host": "192.168.1.5", "tally_port": 9000},
            })

        assert resp.status_code == 201
        body = resp.json()
        assert body["config"]["tally_host"] == "192.168.1.5"


class TestUpdateWorkspace:
    def test_update_workspace_name(self, app):
        ws = _make_mock_workspace(name="Old Name")
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ws
        mock_db.execute.return_value = mock_result

        async def fake_refresh(w):
            w.name = "New Name"

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.patch(f"/api/workspaces/{ws.id}", json={"name": "New Name"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_workspace_config(self, app):
        ws = _make_mock_workspace(config={"tally_host": "old"})
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ws
        mock_db.execute.return_value = mock_result

        async def fake_refresh(w):
            w.config = {"tally_host": "new"}

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.patch(f"/api/workspaces/{ws.id}", json={"config": {"tally_host": "new"}})

        assert resp.status_code == 200
        assert resp.json()["config"]["tally_host"] == "new"

    def test_update_workspace_not_found_404(self, app):
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.patch(f"/api/workspaces/{uuid.uuid4()}", json={"name": "Nope"})

        assert resp.status_code == 404


class TestDeleteWorkspace:
    def test_delete_workspace_success(self, app):
        ws = _make_mock_workspace()
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ws
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.delete(f"/api/workspaces/{ws.id}")

        assert resp.status_code == 204
        assert ws.is_deleted is True

    def test_delete_workspace_not_found_404(self, app):
        mock_db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as tc:
            resp = tc.delete(f"/api/workspaces/{uuid.uuid4()}")

        assert resp.status_code == 404
