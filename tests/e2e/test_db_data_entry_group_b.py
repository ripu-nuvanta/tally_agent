"""E2E tests — Group B voucher-type pipeline in DB mode + audit-row verification.

Requires TEST_DATABASE_URL. Complements the legacy-mode
``tests/e2e/test_data_entry_group_b.py`` by asserting the DB audit trail:

  - Upload persists an ``UploadedFile`` row (status "extracted").
  - A successful write persists a linked ``VoucherEntry`` row (status "written",
    correct ``voucher_type``, ``tally_voucher_number``, and edited ``voucher_data``).
  - Discard creates the ``UploadedFile`` row but NO ``VoucherEntry``.

Only the Claude Vision call is mocked (via ``vision_docs.vision_message`` reusing
the on-disk ``tests/fixtures/vision/*.json`` fixtures); routing, ledger lookup,
party-voucher fetch and the Tally write all run for real against the built-in
mock Tally handler.

The audit ``VoucherEntry`` row is only written when the write entry carries both
``file_id`` and ``conversation_id`` (non-nullable FK) — the frontend threads
these back from the review card. These tests thread them explicitly so the audit
path is genuinely exercised.
"""
import io
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from tests.fixtures import vision_docs

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB Group B data entry tests",
)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


# ---------------------------------------------------------------------------
# App fixture (mirrors tests/e2e/test_db_data_entry.py db_app)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_app(monkeypatch, tmp_path):
    from backend.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", _TEST_DB_URL)
    monkeypatch.setattr(settings, "JWT_SECRET", "a" * 64)
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(
        settings, "ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key")
    )

    from backend.db.models import Base
    setup_engine = create_async_engine(_TEST_DB_URL)
    async with setup_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await setup_engine.dispose()

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

    from backend.agents.context import SessionStore
    from backend.tally_bridge.client import TallyClient
    from backend.db.engine import init_engine

    tally_client = TallyClient(host="localhost", port=9000)
    tally_client.mock_mode = True
    app.state.tally_client = tally_client
    app.state.session_store = SessionStore(ttl_minutes=60)
    init_engine(_TEST_DB_URL)

    auth._register_attempts.clear()
    auth._login_attempts.clear()

    yield app

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
    email = f"gb-{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": "Str0ng!Pass#99", "name": "GB Tester",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user"]["id"]


async def _create_workspace(client: AsyncClient, token: str, name: str) -> str:
    config = {"tally_host": "localhost", "tally_port": 9000,
              "mock_mode": True, "tally_company": "Test Co"}
    resp = await client.post(
        "/api/workspaces",
        json={"name": name, "config": config},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_conversation(client: AsyncClient, token: str, ws_id: str) -> str:
    resp = await client.post(
        f"/api/workspaces/{ws_id}/conversations",
        json={"title": "Group B flow"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _upload(ac, headers, fixture_name, ws_id, conv_id, message="data entry"):
    with patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_docs.vision_message(fixture_name)),
    ):
        return await ac.post(
            "/api/chat/upload",
            files={"file": ("doc.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
            data={"message": message, "workspace_id": ws_id, "conversation_id": conv_id},
            headers=headers,
        )


def _write_entry(review_entry, file_id, conv_id, **overrides):
    """Build a voucher-action write payload, threading file_id + conversation_id
    so the VoucherEntry audit row is persisted."""
    payload = {
        "id": review_entry["id"],
        "voucher_type": review_entry["voucher_type"],
        "date": review_entry["date"],
        "debit_ledger": review_entry["debit_ledger"],
        "credit_ledger": review_entry["credit_ledger"],
        "amount": review_entry["amount"],
        "narration": review_entry["narration"],
        "gst_entries": review_entry.get("gst_entries", []),
        "party_ledger": review_entry.get("party_ledger"),
        "bill_reference": review_entry.get("bill_reference"),
        "is_new_ledger": review_entry.get("is_new_ledger", False),
        "suggested_parent": review_entry.get("suggested_parent"),
        "file_id": file_id,
        "conversation_id": conv_id,
    }
    payload.update(overrides)
    return payload


async def _voucher_entries(file_id):
    """Query VoucherEntry rows linked to a given uploaded-file id."""
    import backend.db.engine as engine_mod
    from backend.db.models import VoucherEntry
    async with engine_mod.async_session_factory() as session:
        rows = (await session.execute(
            select(VoucherEntry).where(VoucherEntry.file_id == uuid.UUID(file_id))
        )).scalars().all()
        return rows


async def _uploaded_file(file_id):
    import backend.db.engine as engine_mod
    from backend.db.models import UploadedFile
    async with engine_mod.async_session_factory() as session:
        return (await session.execute(
            select(UploadedFile).where(UploadedFile.id == uuid.UUID(file_id))
        )).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Purchase (INR) → UploadedFile + VoucherEntry audit rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_purchase_upload_write_creates_audit_rows(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Purchase Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "purchase_office_inr", ws_id, conv_id, "purchase")
        assert up.status_code == 200, up.text
        body = up.json()
        assert body["data"]["type"] == "voucher_review"
        file_id = body["data"]["file_id"]
        entry = body["data"]["entries"][0]
        assert entry["voucher_type"] == "Purchase"

        # UploadedFile row persisted at upload time.
        uf = await _uploaded_file(file_id)
        assert uf is not None
        assert uf.status == "extracted"
        assert uf.extracted_data["doc_type"] == "purchase"

        # Write → VoucherEntry audit row.
        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id),
                "company": "Test Co",
                "session_id": "db-purchase",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"

        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        ve = rows[0]
        assert ve.voucher_type == "Purchase"
        assert ve.status == "written"
        assert ve.tally_voucher_number  # mock returns a vch id
        assert ve.voucher_data["party_ledger"] == "Croma Electronics"


# ---------------------------------------------------------------------------
# Purchase (USD) → INR amount persisted in the audit row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_purchase_usd_writes_inr_audit_row(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "USD Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "purchase_saas_usd", ws_id, conv_id, "usd")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["original_currency"] == "USD"
        inr_amount = entry["amount"]
        assert inr_amount != entry["original_amount"]

        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id),
                "company": "Test Co",
                "session_id": "db-usd",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"

        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        # Audit row records the INR amount that was actually written.
        assert rows[0].voucher_data["amount"] == inr_amount


# ---------------------------------------------------------------------------
# Sales (INR)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_sales_upload_write_creates_audit_rows(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Sales Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "sales_service_inr", ws_id, conv_id, "sales")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["voucher_type"] == "Sales"
        assert entry["party_ledger"] == "Infosys Ltd"

        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id),
                "company": "Test Co",
                "session_id": "db-sales",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"
        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        assert rows[0].voucher_type == "Sales"


# ---------------------------------------------------------------------------
# Debit Note (INR) — against-invoice fetched from the real mock handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_debit_note_against_invoice_write(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "DN Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "debit_note_return_inr", ws_id, conv_id, "dn")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["voucher_type"] == "Debit Note"
        # Croma is seeded in the mock party-voucher map with a prior Purchase.
        assert entry["against_invoice_options"]
        ref = entry["against_invoice_options"][0]["reference"]

        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id, bill_reference=ref),
                "company": "Test Co",
                "session_id": "db-dn",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"
        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        assert rows[0].voucher_type == "Debit Note"
        assert rows[0].voucher_data["bill_reference"] == ref


# ---------------------------------------------------------------------------
# Credit Note (INR)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_credit_note_upload_write(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "CN Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "credit_note_return_inr", ws_id, conv_id, "cn")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["voucher_type"] == "Credit Note"

        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id),
                "company": "Test Co",
                "session_id": "db-cn",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"
        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        assert rows[0].voucher_type == "Credit Note"


# ---------------------------------------------------------------------------
# Discard flow — UploadedFile row created, NO VoucherEntry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_discard_creates_uploaded_file_no_voucher_entry(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Discard Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "purchase_office_inr", ws_id, conv_id, "discard")
        file_id = up.json()["data"]["file_id"]
        entry = up.json()["data"]["entries"][0]

        # UploadedFile exists after upload.
        assert await _uploaded_file(file_id) is not None

        # Discard.
        d = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "discard",
                "entry": {"id": entry["id"], "file_id": file_id,
                          "conversation_id": conv_id},
                "session_id": "db-discard",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert d.status_code == 200, d.text
        assert d.json()["data"]["type"] == "voucher_discarded"

        # No VoucherEntry written for a discarded entry.
        assert await _voucher_entries(file_id) == []


# ---------------------------------------------------------------------------
# Edit + write — audit row carries the EDITED values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_edit_then_write_persists_edited_values(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Edit Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "purchase_office_inr", ws_id, conv_id, "edit")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]

        edited_amount = 9999.0
        edited = _write_entry(
            entry, file_id, conv_id,
            amount=edited_amount,
            narration="Edited before write",
        )
        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "edit",
                "entry": edited,
                "company": "Test Co",
                "session_id": "db-edit",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"

        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        assert rows[0].voucher_data["amount"] == edited_amount
        assert rows[0].voucher_data["narration"] == "Edited before write"


# ---------------------------------------------------------------------------
# Reclassify — Vision says payment; user edits to Purchase, then writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_reclassify_payment_to_purchase(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Reclassify Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "payment_petty_cash_inr", ws_id, conv_id, "petty")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["voucher_type"] == "Payment"

        edited = _write_entry(
            entry, file_id, conv_id,
            voucher_type="Purchase",
            party_ledger="Croma Electronics",
            credit_ledger="Croma Electronics",
            debit_ledger="Purchase - Office Supplies",
            bill_reference="RECLASS-1",
            is_new_ledger=False,
        )
        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "edit",
                "entry": edited,
                "company": "Test Co",
                "session_id": "db-reclassify",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"

        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        # Audit row records the reclassified type, not the original Payment.
        assert rows[0].voucher_type == "Purchase"


# ---------------------------------------------------------------------------
# Regression — original B1a payment/expense path still works + audits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_db_payment_regression_upload_write(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Payment Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        up = await _upload(ac, headers, "payment_petty_cash_inr", ws_id, conv_id, "cab")
        entry = up.json()["data"]["entries"][0]
        file_id = up.json()["data"]["file_id"]
        assert entry["voucher_type"] == "Payment"
        assert entry["is_party_ledger"] is False

        w = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": _write_entry(entry, file_id, conv_id),
                "company": "Test Co",
                "session_id": "db-payment",
                "workspace_id": ws_id,
            },
            headers=headers,
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"
        rows = await _voucher_entries(file_id)
        assert len(rows) == 1
        assert rows[0].voucher_type == "Payment"
