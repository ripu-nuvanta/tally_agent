"""Helpers to load Task-1 Vision fixtures (tests/fixtures/vision/*.json).

These mirror ``tests/fixtures/fx_documents.py`` but read the on-disk JSON
fixtures created in Task 1 (one per doc_type × currency × GST variant). Used by
the Group B orchestrator-routing and DB-audit tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.services.document_parser import ExtractedDocument, parse_vision_response

_VISION_DIR = Path(__file__).parent / "vision"


def vision_json(name: str) -> str:
    """Return the raw JSON string Claude Vision would emit for fixture ``name``."""
    path = _VISION_DIR / f"{name}.json"
    return path.read_text(encoding="utf-8")


def vision_message(name: str) -> MagicMock:
    """Return a MagicMock matching the Anthropic messages.create response."""
    msg = MagicMock()
    msg.content = [MagicMock(text=vision_json(name))]
    return msg


def extracted(name: str) -> ExtractedDocument:
    """Return the fixture parsed into an ``ExtractedDocument``."""
    return parse_vision_response(vision_json(name))
