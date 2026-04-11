"""E2E tests — DB-mode file upload + voucher write pipeline. Requires TEST_DATABASE_URL."""
import importlib
import io
import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB data entry tests",
)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_app(monkeypatch, tmp_path):
    """
    Stand up a full FastAPI app in DB mode with TALLY_WRITE_ENABLED.

    Replicates the module-reload dance from test_db_smoke.py and adds
    file-upload settings (FILE_STORAGE_PATH, TALLY_WRITE_ENABLED).
    """
    # 1. Set env vars before any module reload
    monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("TALLY_MODE", "mock")
    monkeypatch.setenv("TALLY_WRITE_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key"))

    # 2. Reload config so db_mode=True is reflected
    import backend.config
    importlib.reload(backend.config)
    backend.config.settings = backend.config.Settings()
    backend.config.settings.FILE_STORAGE_PATH = str(tmp_path)

    # 3. Reload engine module (it reads settings at import time)
    import backend.db.engine
    importlib.reload(backend.db.engine)

    # 4. Create test DB tables
    from backend.db.models import Base
    setup_engine = create_async_engine(_TEST_DB_URL)
    async with setup_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await setup_engine.dispose()

    # 5. Reload API modules that hold stale references to settings.
    import backend.api.dependencies
    importlib.reload(backend.api.dependencies)
    import backend.api.chat
    importlib.reload(backend.api.chat)
    import backend.api.auth
    importlib.reload(backend.api.auth)
    import backend.api.workspaces
    importlib.reload(backend.api.workspaces)
    import backend.api.conversations
    importlib.reload(backend.api.conversations)
    import backend.api.usage
    importlib.reload(backend.api.usage)

    # Reload main.py — with db_mode=True the auth/workspace/conversation
    # routers are registered at module level.
    import backend.main
    importlib.reload(backend.main)
    from backend.main import app

    # 6. Manually initialise what lifespan would do (ASGITransport skips lifespan)
    from backend.agents.context import SessionStore
    from backend.tally_bridge.client import TallyClient
    from backend.db.engine import init_engine

    tally_client = TallyClient(host="localhost", port=9000)
    tally_client.mock_mode = True
    app.state.tally_client = tally_client
    app.state.session_store = SessionStore(ttl_minutes=60)
    init_engine(_TEST_DB_URL)

    yield app

    # 7. Teardown
    await tally_client.close()
    from backend.db.engine import close_engine
    await close_engine()

    teardown_engine = create_async_engine(_TEST_DB_URL)
    async with teardown_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await teardown_engine.dispose()

    # 8. Restore modules to legacy state so other test files aren't affected
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(backend.config)
    backend.config.settings = backend.config.Settings()
    importlib.reload(backend.db.engine)
    importlib.reload(backend.api.dependencies)
    importlib.reload(backend.api.chat)
    importlib.reload(backend.api.auth)
    importlib.reload(backend.api.workspaces)
    importlib.reload(backend.api.conversations)
    importlib.reload(backend.api.usage)
    importlib.reload(backend.main)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_and_get_token(client: AsyncClient) -> tuple[str, str]:
    """Register a unique user and return (access_token, user_id)."""
    import uuid
    email = f"de-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": "Str0ng!Pass#99", "name": "DE Tester",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user"]["id"]


async def _create_workspace(
    client: AsyncClient, token: str, name: str, tally_company: str = "",
) -> str:
    """Create a workspace and return its id."""
    config = {"tally_host": "localhost", "tally_port": 9000, "mock_mode": True}
    if tally_company:
        config["tally_company"] = tally_company
    resp = await client.post(
        "/api/workspaces",
        json={"name": name, "config": config},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _mock_vision_message(vendor: str, amount: float, date: str) -> MagicMock:
    """Return a MagicMock matching Claude Vision API response structure."""
    vision_text = json.dumps({
        "doc_type": "expense",
        "vendor_name": vendor,
        "date": date,
        "total_amount": amount,
        "line_items": [{"description": "Service", "amount": amount}],
        "gst": None,
        "payment_mode": "upi",
    })
    msg = MagicMock()
    msg.content = [MagicMock(text=vision_text)]
    return msg


_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_upload_receipt_returns_review_card(db_app):
    """Upload a receipt image in DB mode → get a voucher review card."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Upload Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        mock_msg = _mock_vision_message("OfficeMax", 1200.0, "2026-04-05")

        from unittest.mock import patch
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            resp = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={"message": "office supplies", "workspace_id": ws_id},
                headers=headers,
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["type"] == "voucher_review"
        assert len(body["data"]["entries"]) >= 1
        entry = body["data"]["entries"][0]
        assert entry["vendor_name"] == "OfficeMax"
        assert entry["amount"] == 1200.0
        assert entry["status"] == "draft"


@pytest.mark.asyncio
async def test_db_voucher_approve_writes_to_tally(db_app):
    """Upload receipt → approve entry → voucher written to Tally (mock)."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Approve Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Upload receipt
        mock_msg = _mock_vision_message("CabService", 350.0, "2026-04-06")
        from unittest.mock import patch
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            upload_resp = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={"message": "cab expense", "workspace_id": ws_id},
                headers=headers,
            )
        assert upload_resp.status_code == 200, upload_resp.text
        entry = upload_resp.json()["data"]["entries"][0]

        # Step 2: Approve the entry
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": entry.get("id", "test-approve"),
                    "date": entry.get("date", "20260406"),
                    "debit_ledger": entry.get("debit_ledger", "Travel Expenses"),
                    "credit_ledger": entry.get("credit_ledger", "Cash"),
                    "amount": entry["amount"],
                    "narration": entry.get("narration", "CabService expense"),
                    "gst_entries": entry.get("gst_entries", []),
                },
                "company": "Test Co",
                "session_id": "test-session",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "successfully" in body["message"].lower()
        assert body["data"]["type"] == "voucher_written"


@pytest.mark.asyncio
async def test_db_voucher_discard(db_app):
    """Upload receipt → discard entry → confirm discarded."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Discard Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "discard",
                "entry": {"id": "discard-1"},
                "session_id": "test-session",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["type"] == "voucher_discarded"


@pytest.mark.asyncio
async def test_db_voucher_approve_creates_new_ledger(db_app):
    """Approve with is_new_ledger=True → ledger created + voucher created."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "NewLedger Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": "new-ledger-1",
                    "date": "20260405",
                    "debit_ledger": "Fresh Vendor Ltd",
                    "credit_ledger": "Cash",
                    "amount": 750.0,
                    "narration": "First purchase from Fresh Vendor",
                    "gst_entries": [],
                    "is_new_ledger": True,
                    "suggested_parent": "Indirect Expenses",
                },
                "company": "Test Co",
                "session_id": "test-session",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["type"] == "voucher_written"
        assert "successfully" in body["message"].lower()


@pytest.mark.asyncio
async def test_db_upload_requires_workspace_id(db_app):
    """Upload without workspace_id → 400 in DB mode."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post(
            "/api/chat/upload",
            files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
            data={"message": "expense"},
            headers=headers,
        )
        assert resp.status_code == 400, resp.text
        assert "workspace_id" in resp.json()["detail"].lower()
