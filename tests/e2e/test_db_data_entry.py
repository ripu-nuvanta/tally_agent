"""E2E tests — DB-mode file upload + voucher write pipeline. Requires TEST_DATABASE_URL."""
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

    Uses the no-reload pattern (see test_db_smoke.py db_app for the full
    rationale): mutate the shared ``settings`` singleton in place and assemble a
    fresh app, instead of ``importlib.reload`` which rebinds module-level object
    identities and silently breaks other test files' dependency_overrides /
    settings monkeypatches.
    """
    from backend.config import settings

    # 1. Flip the shared singleton into DB mode (restored by monkeypatch).
    monkeypatch.setattr(settings, "DATABASE_URL", _TEST_DB_URL)
    monkeypatch.setattr(settings, "JWT_SECRET", "a" * 64)
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(
        settings, "ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key")
    )

    # 2. Create test DB tables
    from backend.db.models import Base
    setup_engine = create_async_engine(_TEST_DB_URL)
    async with setup_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await setup_engine.dispose()

    # 3. Assemble a fresh app with all routers (DB-mode routers included
    #    unconditionally — auth enforcement is decided at request time).
    from fastapi import FastAPI

    from backend.api import (
        auth,
        chat,
        companies,
        conversations,
        health,
        reports,
        tally_mode,
        usage,
        workspaces,
    )

    app = FastAPI()
    for module in (chat, health, companies, reports, tally_mode,
                   auth, workspaces, conversations, usage):
        app.include_router(module.router, prefix="/api")

    # 4. Manually initialise what lifespan would do (ASGITransport skips lifespan)
    from backend.agents.context import SessionStore
    from backend.tally_bridge.client import TallyClient
    from backend.db.engine import init_engine

    tally_client = TallyClient(host="localhost", port=9000)
    tally_client.mock_mode = True
    app.state.tally_client = tally_client
    app.state.session_store = SessionStore(ttl_minutes=60)
    init_engine(_TEST_DB_URL)

    # Reset auth's in-memory per-IP rate-limit state (was implicitly reset by
    # the old reload; clear it explicitly so it doesn't accumulate across tests).
    auth._register_attempts.clear()
    auth._login_attempts.clear()

    yield app

    # 5. Teardown — close engine + drop tables. settings restored by monkeypatch.
    auth._register_attempts.clear()
    auth._login_attempts.clear()
    await tally_client.close()
    from backend.db.engine import close_engine
    await close_engine()

    teardown_engine = create_async_engine(_TEST_DB_URL)
    async with teardown_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await teardown_engine.dispose()


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


def _mock_fx_vision_message(vendor, amount, date, currency, fx_rate):
    """Vision response with currency + fx_rate fields (FX path)."""
    vision_text = json.dumps({
        "doc_type": "expense",
        "vendor_name": vendor,
        "date": date,
        "currency": currency,
        "fx_rate": fx_rate,
        "total_amount": amount,
        "line_items": [{"description": "Service", "amount": amount}],
        "gst": None,
        "payment_mode": "bank",
    })
    msg = MagicMock()
    msg.content = [MagicMock(text=vision_text)]
    return msg


@pytest.mark.asyncio
async def test_db_fx_upload_override_approve_full_flow(db_app):
    """Full FX flow (T10): upload USD (no rate, blocked) → chat 'use rate 90'
    recomputes INR → approve writes the Payment voucher with the INR amount.

    Requires TEST_DATABASE_URL — the chat rate-override fast path is DB-mode only.
    """
    from unittest.mock import patch
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "FX Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        # A conversation is required for DB-mode chat.
        conv_resp = await ac.post(
            f"/api/workspaces/{ws_id}/conversations",
            json={"title": "FX flow"},
            headers=headers,
        )
        assert conv_resp.status_code in (200, 201), conv_resp.text
        conv_id = conv_resp.json()["id"]

        # Step 1: upload USD doc, no rate, no default configured → blocked card.
        mock_msg = _mock_fx_vision_message("Acme Inc", 100.0, "2026-04-04", "USD", None)
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            up = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={"message": "consulting", "workspace_id": ws_id, "conversation_id": conv_id},
                headers=headers,
            )
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]
        assert entry["original_currency"] == "USD"
        assert entry["original_amount"] == 100.0
        assert entry["fx_rate"] == 0.0
        assert entry["amount"] == 0.0  # blocked: no rate
        assert any("no conversion rate" in w.lower() for w in entry["warnings"])

        # Step 2: chat "use rate 90" WITH pending_entry → recompute, warning cleared.
        chat = await ac.post(
            "/api/chat",
            json={
                "message": "use rate 90",
                "workspace_id": ws_id,
                "conversation_id": conv_id,
                "pending_entry": entry,
            },
            headers=headers,
        )
        assert chat.status_code == 200, chat.text
        cdata = chat.json()
        assert cdata["data"]["type"] == "voucher_review"
        updated = cdata["data"]["entries"][0]
        assert updated["amount"] == 9000.0  # 100 × 90
        assert updated["fx_rate"] == 90.0
        # The FX rate warning must be cleared. A non-blocking "No invoice number"
        # soft note (Phase 1 Part B) may remain — it doesn't gate the write.
        assert not any("rate" in w.lower() for w in updated["warnings"])
        assert "FX: USD 100.00 @ ₹90.00 = ₹9,000.00" in updated["narration"]

        # Step 3: approve → Payment voucher written with the INR amount.
        ap = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": updated["id"],
                    "date": updated.get("date", "20260404"),
                    "debit_ledger": updated.get("debit_ledger", "Consulting Expenses"),
                    "credit_ledger": updated.get("credit_ledger", "Cash"),
                    "amount": updated["amount"],  # 9000 INR
                    "narration": updated["narration"],  # carries FX trail
                    "gst_entries": updated.get("gst_entries", []),
                },
                "company": "Test Co",
                "session_id": "fx-db-e2e",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert ap.status_code == 200, ap.text
        body = ap.json()
        assert body["data"]["type"] == "voucher_written"
        assert "successfully" in body["message"].lower()


async def _create_conversation(client: AsyncClient, token: str, ws_id: str) -> str:
    """Create a conversation in the workspace and return its id."""
    resp = await client.post(
        f"/api/workspaces/{ws_id}/conversations",
        json={"title": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_db_upload_persists_voucher_card_on_reload(db_app):
    """Upload a receipt in DB mode → both the user message and the assistant
    voucher_review card survive a conversation reload (previously they did NOT
    persist), and the conversation gets an upload-first title."""
    from unittest.mock import patch
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Reload Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        mock_msg = _mock_vision_message("OfficeMax", 1200.0, "2026-04-05")
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            resp = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={
                    "message": "office supplies",
                    "workspace_id": ws_id,
                    "conversation_id": conv_id,
                },
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["type"] == "voucher_review"

        # RELOAD the conversation — messages + card must now be persisted.
        reload = await ac.get(
            f"/api/workspaces/{ws_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert reload.status_code == 200, reload.text
        conv = reload.json()
        messages = conv["messages"]
        assert len(messages) >= 2, f"expected >=2 persisted messages, got {messages}"

        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("[receipt.jpg]" in m["content"] for m in user_msgs), (
            f"no user message carrying the filename in [...]: {user_msgs}"
        )

        assistant_cards = [
            m for m in messages
            if m["role"] == "assistant"
            and isinstance(m["data"], dict)
            and m["data"].get("type") == "voucher_review"
        ]
        assert assistant_cards, f"no persisted voucher_review card: {messages}"
        entry = assistant_cards[0]["data"]["entries"][0]
        assert entry["vendor_name"] == "OfficeMax"
        assert entry["amount"] == 1200.0

        # Upload-first title fix: conversation is titled after the upload.
        assert conv["title"], f"conversation title still null after upload: {conv}"


@pytest.mark.asyncio
async def test_db_upload_approve_persists_written_status_on_reload(db_app):
    """Upload → approve (conv_id threaded via REQUEST body, not the entry) →
    the originating card's entry status reads 'written' after reload, and a
    VoucherEntry audit row exists for the conversation."""
    from unittest.mock import patch
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "ApproveReload Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        mock_msg = _mock_vision_message("CabService", 350.0, "2026-04-06")
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            up = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={
                    "message": "cab expense",
                    "workspace_id": ws_id,
                    "conversation_id": conv_id,
                },
                headers=headers,
            )
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        # Approve — conversation_id goes in the REQUEST body (mirrors production:
        # the entry dict never carries it). Writes succeed via mock Tally mode.
        approve = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": entry.get("id", "approve-reload"),
                    "date": entry.get("date", "20260406"),
                    "debit_ledger": entry.get("debit_ledger", "Travel Expenses"),
                    "credit_ledger": entry.get("credit_ledger", "Cash"),
                    "amount": entry["amount"],
                    "narration": entry.get("narration", "CabService expense"),
                    "gst_entries": entry.get("gst_entries", []),
                },
                "company": "Test Co",
                "session_id": "approve-reload-session",
                "workspace_id": ws_id,
                "conversation_id": conv_id,
            },
            headers=headers,
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["data"]["type"] == "voucher_written", approve.text

        # RELOAD — the card's entry status must now read 'written'.
        reload = await ac.get(
            f"/api/workspaces/{ws_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert reload.status_code == 200, reload.text
        cards = [
            m for m in reload.json()["messages"]
            if m["role"] == "assistant"
            and isinstance(m["data"], dict)
            and m["data"].get("type") == "voucher_review"
        ]
        assert cards, "no persisted voucher_review card after approve"
        reloaded_entry = cards[0]["data"]["entries"][0]
        assert reloaded_entry["status"] == "written", (
            f"expected status 'written', got {reloaded_entry.get('status')!r}"
        )

        # A VoucherEntry audit row must exist for this conversation.
        from sqlalchemy import select as _select
        from backend.db.models import VoucherEntry as VoucherEntryDB
        audit_engine = create_async_engine(_TEST_DB_URL)
        try:
            async with audit_engine.connect() as conn:
                res = await conn.execute(
                    _select(VoucherEntryDB.status).where(
                        VoucherEntryDB.conversation_id == conv_id
                    )
                )
                statuses = [r[0] for r in res.fetchall()]
        finally:
            await audit_engine.dispose()
        assert statuses, "no VoucherEntry audit row persisted for the conversation"
        assert "written" in statuses, f"audit row statuses: {statuses}"


@pytest.mark.asyncio
async def test_db_upload_discard_persists_deleted_status_on_reload(db_app):
    """Upload → discard (conv_id via request body) → the card's entry status
    reads 'deleted' after reload."""
    from unittest.mock import patch
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "DiscardReload Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        mock_msg = _mock_vision_message("OfficeMax", 800.0, "2026-04-07")
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=mock_msg),
        ):
            up = await ac.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
                data={
                    "message": "office supplies",
                    "workspace_id": ws_id,
                    "conversation_id": conv_id,
                },
                headers=headers,
            )
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        discard = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "discard",
                "entry": {"id": entry.get("id", "discard-reload")},
                "session_id": "discard-reload-session",
                "workspace_id": ws_id,
                "conversation_id": conv_id,
            },
            headers=headers,
        )
        assert discard.status_code == 200, discard.text
        assert discard.json()["data"]["type"] == "voucher_discarded", discard.text

        # RELOAD — the card's entry status must now read 'deleted'.
        reload = await ac.get(
            f"/api/workspaces/{ws_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert reload.status_code == 200, reload.text
        cards = [
            m for m in reload.json()["messages"]
            if m["role"] == "assistant"
            and isinstance(m["data"], dict)
            and m["data"].get("type") == "voucher_review"
        ]
        assert cards, "no persisted voucher_review card after discard"
        reloaded_entry = cards[0]["data"]["entries"][0]
        assert reloaded_entry["status"] == "deleted", (
            f"expected status 'deleted', got {reloaded_entry.get('status')!r}"
        )


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
