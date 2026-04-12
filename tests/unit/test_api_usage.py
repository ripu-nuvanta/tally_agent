"""Tests for GET /api/usage endpoint."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.usage import router
from backend.api.dependencies import get_current_user
from backend.db.engine import get_db


USER_ID = str(uuid.uuid4())
WORKSPACE_ID_1 = str(uuid.uuid4())
WORKSPACE_ID_2 = str(uuid.uuid4())


def _make_usage_log(workspace_id=None, input_tokens=100, output_tokens=50,
                    cost_usd=0.001, created_at=None):
    log = MagicMock()
    log.workspace_id = workspace_id or uuid.UUID(WORKSPACE_ID_1)
    log.total_input_tokens = input_tokens
    log.total_output_tokens = output_tokens
    log.total_cost_usd = Decimal(str(cost_usd))
    log.created_at = created_at or datetime(2026, 4, 1, tzinfo=timezone.utc)
    return log


def _make_mock_workspace(ws_id, name="Test Co"):
    ws = MagicMock()
    ws.id = uuid.UUID(ws_id) if isinstance(ws_id, str) else ws_id
    ws.name = name
    return ws


def _make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(router, prefix="/api")
    a.dependency_overrides[get_current_user] = lambda: USER_ID
    return a


# ---------------------------------------------------------------------------
# Test 1: usage totals — sums tokens and cost across all logs
# ---------------------------------------------------------------------------

def test_usage_totals(app):
    """Returns correct aggregated totals across multiple usage log rows."""
    log1 = _make_usage_log(input_tokens=100, output_tokens=50, cost_usd=0.001)
    log2 = _make_usage_log(input_tokens=200, output_tokens=80, cost_usd=0.002)

    mock_db = _make_mock_db()

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [log1, log2]

    ws_result = MagicMock()
    ws_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [logs_result, ws_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.get("/api/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_input_tokens"] == 300
    assert body["total_output_tokens"] == 130
    assert abs(body["total_cost_usd"] - 0.003) < 1e-9


# ---------------------------------------------------------------------------
# Test 2: by_workspace breakdown — groups logs by workspace
# ---------------------------------------------------------------------------

def test_usage_by_workspace(app):
    """Aggregates usage grouped by workspace with name enrichment."""
    ws_uuid_1 = uuid.UUID(WORKSPACE_ID_1)
    ws_uuid_2 = uuid.UUID(WORKSPACE_ID_2)

    log1 = _make_usage_log(workspace_id=ws_uuid_1, cost_usd=0.001)
    log2 = _make_usage_log(workspace_id=ws_uuid_1, cost_usd=0.002)
    log3 = _make_usage_log(workspace_id=ws_uuid_2, cost_usd=0.005)

    mock_db = _make_mock_db()

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [log1, log2, log3]

    ws1 = _make_mock_workspace(WORKSPACE_ID_1, "Company A")
    ws2 = _make_mock_workspace(WORKSPACE_ID_2, "Company B")
    ws_result = MagicMock()
    ws_result.scalars.return_value.all.return_value = [ws1, ws2]

    mock_db.execute.side_effect = [logs_result, ws_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.get("/api/usage")

    assert resp.status_code == 200
    body = resp.json()
    by_ws = {item["workspace_id"]: item for item in body["by_workspace"]}

    assert WORKSPACE_ID_1 in by_ws
    assert WORKSPACE_ID_2 in by_ws
    assert by_ws[WORKSPACE_ID_1]["message_count"] == 2
    assert by_ws[WORKSPACE_ID_2]["message_count"] == 1
    assert by_ws[WORKSPACE_ID_1]["name"] == "Company A"
    assert by_ws[WORKSPACE_ID_2]["name"] == "Company B"


# ---------------------------------------------------------------------------
# Test 3: by_day breakdown — groups logs by calendar date, sorted
# ---------------------------------------------------------------------------

def test_usage_by_day(app):
    """Groups usage logs by date and sorts chronologically."""
    log1 = _make_usage_log(cost_usd=0.001,
                           created_at=datetime(2026, 4, 1, tzinfo=timezone.utc))
    log2 = _make_usage_log(cost_usd=0.002,
                           created_at=datetime(2026, 4, 3, tzinfo=timezone.utc))
    log3 = _make_usage_log(cost_usd=0.003,
                           created_at=datetime(2026, 4, 1, tzinfo=timezone.utc))

    mock_db = _make_mock_db()

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = [log1, log2, log3]

    ws_result = MagicMock()
    ws_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [logs_result, ws_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.get("/api/usage")

    assert resp.status_code == 200
    body = resp.json()
    by_day = body["by_day"]

    # Should be sorted chronologically
    assert len(by_day) == 2
    assert by_day[0]["date"] == "2026-04-01"
    assert by_day[1]["date"] == "2026-04-03"
    assert by_day[0]["message_count"] == 2
    assert by_day[1]["message_count"] == 1


# ---------------------------------------------------------------------------
# Test 4: empty state — no usage logs returns zero totals
# ---------------------------------------------------------------------------

def test_usage_empty_state(app):
    """When no usage logs exist, totals are zero and lists are empty."""
    mock_db = _make_mock_db()

    logs_result = MagicMock()
    logs_result.scalars.return_value.all.return_value = []

    # by_workspace is empty so the second execute for workspace names is NOT called
    mock_db.execute.return_value = logs_result
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as tc:
        resp = tc.get("/api/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_input_tokens"] == 0
    assert body["total_output_tokens"] == 0
    assert body["total_cost_usd"] == 0.0
    assert body["by_workspace"] == []
    assert body["by_day"] == []
