"""E2E test for expense data entry pipeline (mock mode)."""
import io
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    # Force legacy (non-DB) mode so auth dependency is a no-op, even if the
    # developer has DATABASE_URL set in .env (Set A1 default).
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    monkeypatch.setattr(settings, "JWT_SECRET", None)
    from backend.main import app
    with TestClient(app) as tc:
        yield tc


class TestDataEntryE2E:
    def test_upload_receipt_returns_review_card(self, client):
        """Upload a receipt image → get back a voucher review card."""
        # Mock Claude Vision response
        vision_response_text = json.dumps({
            "doc_type": "expense",
            "vendor_name": "Uber",
            "date": "2026-04-04",
            "total_amount": 500.0,
            "line_items": [{"description": "Ride", "amount": 500.0}],
            "gst": None,
            "payment_mode": "upi",
        })

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=vision_response_text)]

        mock_anthropic_instance = MagicMock()
        mock_anthropic_instance.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_anthropic_instance):
            file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 200
            response = client.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"message": "lunch expense"},
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert "Uber" in data["message"]
        assert data["data"]["type"] == "voucher_review"
        assert len(data["data"]["entries"]) == 1
        entry = data["data"]["entries"][0]
        assert entry["status"] == "draft"
        assert entry["vendor_name"] == "Uber"
        assert entry["amount"] == 500.0

    def test_voucher_approve_writes_to_tally(self, client):
        """Posting approve action should call the writer (mock mode)."""
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": "test-1",
                    "date": "20260404",
                    "debit_ledger": "Travel Expenses",
                    "credit_ledger": "Cash",
                    "amount": 500.0,
                    "narration": "Uber ride",
                    "gst_entries": [],
                },
                "company": "Test Co",
                "session_id": "test-session",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["data"]["type"] == "voucher_written"
        assert "successfully" in data["message"].lower()

    def test_voucher_discard(self, client):
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "discard",
                "entry": {"id": "test-1"},
                "session_id": "test-session",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["type"] == "voucher_discarded"

    def test_voucher_edit_writes_to_tally(self, client):
        """Edit action should be treated as approve — writes the (possibly edited) entry."""
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "edit",
                "entry": {
                    "id": "test-edit",
                    "date": "20260302",
                    "debit_ledger": "Bank Charges",
                    "credit_ledger": "Cash",
                    "amount": 123.45,
                    "narration": "Edited entry test",
                    "gst_entries": [],
                },
                "company": "Test Co",
                "session_id": "test",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["data"]["type"] == "voucher_written"

    def test_voucher_approve_creates_new_ledger_first(self, client):
        """When is_new_ledger=True, backend must create the ledger before the voucher."""
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "approve",
                "entry": {
                    "id": "test-new",
                    "date": "20260302",
                    "debit_ledger": "Brand New Vendor Inc",
                    "credit_ledger": "Cash",
                    "amount": 100.00,
                    "narration": "First time vendor",
                    "gst_entries": [],
                    "is_new_ledger": True,
                    "suggested_parent": "Indirect Expenses",
                },
                "company": "Test Co",
                "session_id": "test",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # Mock handler returns success for both ledger and voucher create
        assert data["data"]["type"] == "voucher_written"

    def test_voucher_action_missing_required_field(self, client):
        """Missing action field → 422 validation error."""
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "entry": {"id": "x"},
                "company": "Test Co",
            },
        )
        assert response.status_code == 422

    def test_voucher_action_unknown_action(self, client):
        """Unknown action → 422 from Literal validation."""
        response = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "explode",
                "entry": {"id": "x"},
                "company": "Test Co",
            },
        )
        assert response.status_code == 422
