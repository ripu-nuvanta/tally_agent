"""Tests for file upload endpoint."""
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI client with file storage redirected to tmp path."""
    from backend.config import settings
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    from backend.main import app
    with TestClient(app) as c:
        yield c


class TestFileUploadEndpoint:
    def test_upload_jpg_returns_success(self, client):
        file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
        response = client.post(
            "/api/chat/upload",
            files={"file": ("receipt.jpg", io.BytesIO(file_content), "image/jpeg")},
            data={"message": "lunch expense"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "uploaded" in data["message"].lower()
        assert data["data"]["type"] == "file_uploaded"
        assert data["data"]["filename"] == "receipt.jpg"

    def test_upload_pdf_returns_success(self, client):
        file_content = b"%PDF-1.4" + b"\x00" * 100
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
