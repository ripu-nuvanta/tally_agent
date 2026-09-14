"""Tests for file upload endpoint."""
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI client with file storage redirected to tmp path."""
    from backend.config import settings
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    # Force legacy (non-DB) mode so auth dependency is a no-op, even if the
    # developer has DATABASE_URL set in .env (Set A1 default).
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    monkeypatch.setattr(settings, "JWT_SECRET", None)
    # Tests that write vouchers need the write flag enabled (default is False).
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    from backend.main import app
    with TestClient(app) as c:
        yield c


def _mock_vision_message(
    vendor: str = "Uber",
    amount: float = 500.0,
    currency: str = "INR",
    fx_rate=None,
):
    """Build a fake Claude Vision response message."""
    vision_response_text = json.dumps({
        "doc_type": "expense",
        "vendor_name": vendor,
        "date": "2026-04-04",
        "currency": currency,
        "fx_rate": fx_rate,
        "total_amount": amount,
        "line_items": [{"description": "Test", "amount": amount}],
        "gst": None,
        "payment_mode": "upi",
    })
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=vision_response_text)]
    return mock_message


def _upload(client, vision_message, filename="receipt.jpg", mime="image/jpeg", message="expense"):
    file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    with patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_message),
    ):
        return client.post(
            "/api/chat/upload",
            files={"file": (filename, io.BytesIO(file_content), mime)},
            data={"message": message},
        )


class TestFileUploadEndpoint:
    def test_upload_jpg_returns_success(self, client):
        file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=_mock_vision_message()),
        ):
            response = client.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"message": "lunch expense"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["type"] == "voucher_review"
        assert data["data"]["entries"][0]["vendor_name"] == "Uber"

    def test_upload_pdf_returns_success(self, client):
        file_content = b"%PDF-1.4" + b"\x00" * 100
        with patch(
            "backend.agents.orchestrator.anthropic_client.messages.create",
            new=AsyncMock(return_value=_mock_vision_message()),
        ):
            response = client.post(
                "/api/chat/upload",
                files={"file": ("invoice.pdf", io.BytesIO(file_content), "application/pdf")},
            )
        assert response.status_code == 200

    def test_upload_unsupported_type(self, client):
        response = client.post(
            "/api/chat/upload",
            files={"file": ("doc.docx", io.BytesIO(b"content"), "application/msword")},
        )
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_upload_too_large(self, client, monkeypatch):
        from backend.config import settings
        # Set max to 0 MB so any file is too large
        monkeypatch.setattr(settings, "FILE_MAX_SIZE_MB", 0)
        response = client.post(
            "/api/chat/upload",
            files={"file": ("big.jpg", io.BytesIO(b"\x00" * 1000), "image/jpeg")},
        )
        assert response.status_code == 400
        assert "large" in response.json()["detail"].lower()

    def test_upload_empty_file(self, client):
        response = client.post(
            "/api/chat/upload",
            files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()


class TestFileUploadFxFields:
    """T6 — voucher_review entry carries FX fields and rate warnings."""

    def test_inr_doc_unchanged(self, client):
        resp = _upload(client, _mock_vision_message(amount=500.0, currency="INR"))
        assert resp.status_code == 200
        entry = resp.json()["data"]["entries"][0]
        assert entry["original_currency"] == "INR"
        assert entry["original_amount"] == 500.0
        assert entry["fx_rate"] == 1.0
        assert entry["amount"] == 500.0
        assert entry["original_gst_entries"] == []
        # No FX warning for INR docs
        assert not any("rate" in w.lower() for w in entry["warnings"])

    def test_usd_doc_with_doc_rate(self, client):
        resp = _upload(
            client, _mock_vision_message(amount=100.0, currency="USD", fx_rate=83.5)
        )
        assert resp.status_code == 200
        entry = resp.json()["data"]["entries"][0]
        assert entry["original_currency"] == "USD"
        assert entry["original_amount"] == 100.0
        assert entry["fx_rate"] == 83.5
        assert entry["amount"] == 8350.0
        assert "original_gst_entries" in entry
        # doc rate -> no warning
        assert not any("default" in w.lower() or "no conversion" in w.lower()
                       for w in entry["warnings"])

    def test_usd_doc_no_rate_uses_default(self, client, monkeypatch):
        from backend.config import settings
        monkeypatch.setattr(settings, "FX_DEFAULT_RATES", "USD:80")
        monkeypatch.setattr(settings, "FX_DEFAULT_RATE", 0.0)
        resp = _upload(
            client, _mock_vision_message(amount=100.0, currency="USD", fx_rate=None)
        )
        assert resp.status_code == 200
        entry = resp.json()["data"]["entries"][0]
        assert entry["fx_rate"] == 80.0
        assert entry["amount"] == 8000.0
        assert any("default" in w.lower() and "use rate" in w.lower()
                   for w in entry["warnings"])

    def test_usd_doc_no_rate_no_default_blocked(self, client, monkeypatch):
        from backend.config import settings
        monkeypatch.setattr(settings, "FX_DEFAULT_RATES", "")
        monkeypatch.setattr(settings, "FX_DEFAULT_RATE", 0.0)
        resp = _upload(
            client, _mock_vision_message(amount=100.0, currency="USD", fx_rate=None)
        )
        assert resp.status_code == 200
        entry = resp.json()["data"]["entries"][0]
        assert entry["fx_rate"] == 0.0
        assert entry["amount"] == 0.0
        assert any("no conversion rate" in w.lower() for w in entry["warnings"])
