"""Tests for file upload endpoint."""
import io
import json
from unittest.mock import MagicMock, patch

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


def _mock_vision_client(vendor: str = "Uber", amount: float = 500.0):
    """Build a MagicMock anthropic.Anthropic replacement returning a fake extraction."""
    vision_response_text = json.dumps({
        "doc_type": "expense",
        "vendor_name": vendor,
        "date": "2026-04-04",
        "total_amount": amount,
        "line_items": [{"description": "Test", "amount": amount}],
        "gst": None,
        "payment_mode": "upi",
    })
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=vision_response_text)]
    mock_instance = MagicMock()
    mock_instance.messages.create.return_value = mock_message
    return mock_instance


class TestFileUploadEndpoint:
    def test_upload_jpg_returns_success(self, client):
        file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
        with patch("anthropic.Anthropic", return_value=_mock_vision_client()):
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
        with patch("anthropic.Anthropic", return_value=_mock_vision_client()):
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
