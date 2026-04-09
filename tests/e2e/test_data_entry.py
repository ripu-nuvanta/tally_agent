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
