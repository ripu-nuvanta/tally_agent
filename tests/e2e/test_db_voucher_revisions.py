"""E2E tests — DB-mode voucher edit-history / version trail.

Verifies the ``voucher_entry_revisions`` table records a full, queryable
version trail (upload v1 → edits → write) for each review-card entry. The
trail is DB-only (not shown in the chat UI). Requires TEST_DATABASE_URL.

Reuses the ``db_app`` fixture + helpers from test_db_data_entry.py.
"""
import io
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.e2e.test_db_data_entry import (
    db_app,  # noqa: F401  (pytest fixture)
    _register_and_get_token,
    _create_workspace,
    _mock_vision_message,
    _FAKE_JPEG,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB revision tests",
)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_conversation(ac, token, ws_id):
    """Create a real conversation and return its id (revisions need it)."""
    resp = await ac.post(
        f"/api/workspaces/{ws_id}/conversations",
        json={"title": "Rev Test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _fetch_revisions(conversation_id, entry_id):
    """Query the voucher_entry_revisions trail ordered by version_no."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from backend.db.models import VoucherEntryRevision

    engine = create_async_engine(_TEST_DB_URL)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        rows = (
            await s.execute(
                select(VoucherEntryRevision)
                .where(
                    VoucherEntryRevision.conversation_id == conversation_id,
                    VoucherEntryRevision.entry_id == entry_id,
                )
                .order_by(VoucherEntryRevision.version_no)
            )
        ).scalars().all()
        # Detach by reading attributes now.
        out = [
            {
                "version_no": r.version_no,
                "source": r.source,
                "voucher_data": dict(r.voucher_data),
                "file_id": str(r.file_id) if r.file_id is not None else None,
            }
            for r in rows
        ]
    await engine.dispose()
    return out


async def _upload(ac, token, ws_id, conv_id, vendor="OfficeMax", amount=1200.0):
    """Upload a receipt into a real conversation and return the card entry dict."""
    headers = {"Authorization": f"Bearer {token}"}
    mock_msg = _mock_vision_message(vendor, amount, "2026-04-05")
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
    return resp.json()["data"]["entries"][0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revision_v1_recorded_on_upload(db_app):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev Up Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)

        entry = await _upload(ac, token, ws_id, conv_id, vendor="OfficeMax", amount=1200.0)

        trail = await _fetch_revisions(conv_id, entry["id"])
        assert len(trail) == 1
        assert trail[0]["version_no"] == 1
        assert trail[0]["source"] == "upload"
        # Snapshot matches the card.
        assert trail[0]["voucher_data"]["vendor_name"] == "OfficeMax"
        assert trail[0]["voucher_data"]["amount"] == 1200.0
        assert trail[0]["voucher_data"]["id"] == entry["id"]


@pytest.mark.asyncio
async def test_revision_recorded_on_each_edit(db_app):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev Edit Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        entry = await _upload(ac, token, ws_id, conv_id)
        entry_id = entry["id"]

        # Edit 1: change reference.
        edit1 = dict(entry)
        edit1["reference"] = "INV-001"
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "save_draft",
                "entry": edit1,
                "workspace_id": ws_id,
                "conversation_id": conv_id,
                "session_id": "s",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        # Edit 2: change amount.
        edit2 = dict(edit1)
        edit2["amount"] = 1500.0
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "save_draft",
                "entry": edit2,
                "workspace_id": ws_id,
                "conversation_id": conv_id,
                "session_id": "s",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        trail = await _fetch_revisions(conv_id, entry_id)
        assert [r["version_no"] for r in trail] == [1, 2, 3]
        assert [r["source"] for r in trail] == ["upload", "edit", "edit"]
        # Each edit snapshot carries that edit's values.
        assert trail[1]["voucher_data"]["reference"] == "INV-001"
        assert trail[2]["voucher_data"]["amount"] == 1500.0
        # v1 (original) still present and UNCHANGED.
        assert trail[0]["voucher_data"]["amount"] == 1200.0
        assert trail[0]["voucher_data"].get("reference") in (None, entry.get("reference"))


@pytest.mark.asyncio
async def test_revision_recorded_on_write(db_app):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev Write Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        entry = await _upload(ac, token, ws_id, conv_id, vendor="CabService", amount=350.0)
        entry_id = entry["id"]

        approve_entry = {
            "id": entry_id,
            "date": entry.get("date", "20260406"),
            "debit_ledger": entry.get("debit_ledger", "Travel Expenses"),
            "credit_ledger": entry.get("credit_ledger", "Cash"),
            "amount": entry["amount"],
            "narration": entry.get("narration", "CabService expense"),
            "gst_entries": [],
        }
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": approve_entry,
                "company": "Test Co",
                "workspace_id": ws_id,
                "conversation_id": conv_id,
                "session_id": "s",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["type"] == "voucher_written", resp.text

        trail = await _fetch_revisions(conv_id, entry_id)
        # upload v1 + write at highest version.
        assert trail[0]["source"] == "upload"
        assert trail[-1]["source"] == "write"
        assert trail[-1]["version_no"] == max(r["version_no"] for r in trail)


@pytest.mark.asyncio
async def test_full_trail_queryback(db_app):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev Trail Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        entry = await _upload(ac, token, ws_id, conv_id, vendor="OfficeMax", amount=1200.0)
        entry_id = entry["id"]
        original_v1 = json.dumps(
            (await _fetch_revisions(conv_id, entry_id))[0]["voucher_data"],
            sort_keys=True,
        )

        # One edit.
        edit1 = dict(entry)
        edit1["narration"] = "edited narration"
        await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "save_draft", "entry": edit1, "workspace_id": ws_id,
                "conversation_id": conv_id, "session_id": "s",
            },
            headers=headers,
        )

        # Write.
        await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": entry_id, "date": "20260405",
                    "debit_ledger": "Travel Expenses", "credit_ledger": "Cash",
                    "amount": 1200.0, "narration": "edited narration", "gst_entries": [],
                },
                "company": "Test Co", "workspace_id": ws_id,
                "conversation_id": conv_id, "session_id": "s",
            },
            headers=headers,
        )

        trail = await _fetch_revisions(conv_id, entry_id)
        assert [r["version_no"] for r in trail] == [1, 2, 3]
        assert [r["source"] for r in trail] == ["upload", "edit", "write"]
        # Original v1 snapshot byte-stable across later edits.
        v1_now = json.dumps(trail[0]["voucher_data"], sort_keys=True)
        assert v1_now == original_v1


@pytest.mark.asyncio
async def test_revision_v1_carries_file_id_joinable_to_uploaded_file(db_app):  # noqa: F811
    """The v1 (upload) revision must hard-link to the original upload via file_id.

    Asserts: (1) the card entry carries file_id, (2) the v1 revision row's
    file_id equals it, and (3) entry.file_id JOINs to a real uploaded_files row
    in the same conversation.
    """
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev FileId Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)

        entry = await _upload(ac, token, ws_id, conv_id, vendor="OfficeMax", amount=1200.0)

        # The card entry carries the uploaded-file id.
        assert entry.get("file_id"), "card entry must carry file_id"
        entry_file_id = entry["file_id"]

        # The v1 revision row carries the same file_id.
        trail = await _fetch_revisions(conv_id, entry["id"])
        assert len(trail) == 1
        assert trail[0]["file_id"] == entry_file_id

        # entry.file_id JOINs to a real uploaded_files row in this conversation.
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from backend.db.models import UploadedFile

        engine = create_async_engine(_TEST_DB_URL)
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            uf = (
                await s.execute(
                    select(UploadedFile).where(
                        UploadedFile.id == entry_file_id,
                        UploadedFile.conversation_id == conv_id,
                    )
                )
            ).scalar_one_or_none()
        await engine.dispose()
        assert uf is not None, "entry.file_id must join to an uploaded_files row"


@pytest.mark.asyncio
async def test_write_path_carries_file_id(db_app):  # noqa: F811
    """The write path must propagate file_id to BOTH the voucher_entries audit
    row and the 'write' revision row, each joinable to the upload.

    Asserts: (a) the voucher_entries audit row for this entry has file_id ==
    the upload's id (not null); (b) the source='write' revision carries the same
    file_id; (c) both JOIN to a real uploaded_files row in this conversation.
    """
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev WriteFid Co", tally_company="Test Co")
        conv_id = await _create_conversation(ac, token, ws_id)
        headers = {"Authorization": f"Bearer {token}"}

        entry = await _upload(ac, token, ws_id, conv_id, vendor="CabService", amount=350.0)
        entry_id = entry["id"]
        upload_file_id = entry.get("file_id")
        assert upload_file_id, "card entry must carry file_id"

        approve_entry = {
            "id": entry_id,
            "file_id": upload_file_id,
            "date": entry.get("date", "20260406"),
            "debit_ledger": entry.get("debit_ledger", "Travel Expenses"),
            "credit_ledger": entry.get("credit_ledger", "Cash"),
            "amount": entry["amount"],
            "narration": entry.get("narration", "CabService expense"),
            "gst_entries": [],
        }
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": approve_entry,
                "company": "Test Co",
                "workspace_id": ws_id,
                "conversation_id": conv_id,
                "session_id": "s",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["type"] == "voucher_written", resp.text

        # (b) The 'write' revision row carries the upload's file_id.
        trail = await _fetch_revisions(conv_id, entry_id)
        write_revs = [r for r in trail if r["source"] == "write"]
        assert len(write_revs) == 1, trail
        assert write_revs[0]["file_id"] == upload_file_id

        # (a) The voucher_entries audit row carries the upload's file_id.
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from backend.db.models import VoucherEntry as VoucherEntryDB, UploadedFile

        engine = create_async_engine(_TEST_DB_URL)
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            ve = (
                await s.execute(
                    select(VoucherEntryDB).where(
                        VoucherEntryDB.conversation_id == conv_id,
                        VoucherEntryDB.voucher_data["id"].astext == entry_id,
                    )
                )
            ).scalar_one_or_none()
            assert ve is not None, "voucher_entries audit row must exist"
            assert ve.file_id is not None, "audit row file_id must not be null"
            assert str(ve.file_id) == upload_file_id

            # (c) Both file_ids JOIN to a real uploaded_files row in this conv.
            uf = (
                await s.execute(
                    select(UploadedFile).where(
                        UploadedFile.id == ve.file_id,
                        UploadedFile.conversation_id == conv_id,
                    )
                )
            ).scalar_one_or_none()
            assert uf is not None, "audit row file_id must join to uploaded_files"
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_conversation_id_skips_revision_gracefully(db_app):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        token, _ = await _register_and_get_token(ac)
        ws_id = await _create_workspace(ac, token, "Rev NoConv Co", tally_company="Test Co")
        headers = {"Authorization": f"Bearer {token}"}

        # save_draft with NO conversation_id — must not crash, records nothing.
        resp = await ac.post(
            "/api/chat/voucher-action",
            json={
                "action": "save_draft",
                "entry": {"id": "no-conv-1", "amount": 99.0},
                "workspace_id": ws_id,
                "session_id": "s",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

        # No revisions exist for that entry id (no conversation to query, but
        # confirm a global lookup finds nothing).
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from backend.db.models import VoucherEntryRevision

        engine = create_async_engine(_TEST_DB_URL)
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            rows = (
                await s.execute(
                    select(VoucherEntryRevision).where(
                        VoucherEntryRevision.entry_id == "no-conv-1"
                    )
                )
            ).scalars().all()
        await engine.dispose()
        assert rows == []
