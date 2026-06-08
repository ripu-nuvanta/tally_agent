"""Reusable FX → INR conversion test fixtures (T9).

This codebase has no JSON *file* fixtures for extracted documents — every
extraction test builds the Vision response inline as a dict / JSON string (see
``tests/unit/test_file_upload_endpoint.py`` and ``tests/e2e/test_data_entry.py``).
Following that convention, these fixtures live as reusable Python dicts in the
SAME format the code consumes: the JSON object Claude Vision returns and that
``backend.services.document_parser.parse_vision_response`` parses into an
``ExtractedDocument``.

Each fixture is the raw Vision-response payload. Helpers turn one into:
  - a JSON string / mocked Anthropic message (``vision_message`` / ``vision_json``)
    for the upload endpoint path, or
  - a parsed ``ExtractedDocument`` (``extracted``) for builder-level tests.

Fixture matrix (from the spec § Fixture matrix):
  - expense_usd_with_rate   — USD, fx_rate printed (83.5).
  - expense_usd_no_rate     — USD, fx_rate null.
  - expense_eur_no_rate     — EUR, fx_rate null (per-currency default).
  - expense_inr             — INR regression (currency INR), fx_rate null.
  - expense_usd_with_gst    — USD + GST breakdown (CGST/SGST legs).

NOTE on ``expense_usd_with_gst``: the document-upload path
(``Orchestrator.process_file_upload``) calls ``build_payment_voucher_data``
WITHOUT ``gst_ledgers``, so GST legs intentionally come out EMPTY through the
upload endpoint (only the total is converted). GST-leg scaling is therefore
exercised at the BUILDER level, where ``gst_ledgers`` can be passed — use
``extracted("expense_usd_with_gst")`` with
``build_payment_voucher_data(..., gst_ledgers=...)``.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from backend.services.document_parser import ExtractedDocument, parse_vision_response

# ---------------------------------------------------------------------------
# Vision-response payloads (the JSON Claude Vision returns)
# ---------------------------------------------------------------------------

FX_DOCUMENTS: dict[str, dict] = {
    # USD with an exchange rate printed on the document → rate source "document".
    "expense_usd_with_rate": {
        "doc_type": "expense",
        "vendor_name": "Acme Inc",
        "date": "2026-04-04",
        "currency": "USD",
        "fx_rate": 83.5,
        "total_amount": 100.0,
        "line_items": [{"description": "Consulting", "amount": 100.0}],
        "gst": None,
        "payment_mode": "bank",
    },
    # USD, no rate printed → falls back to configured default / fallback / none.
    "expense_usd_no_rate": {
        "doc_type": "expense",
        "vendor_name": "Globex LLC",
        "date": "2026-04-05",
        "currency": "USD",
        "fx_rate": None,
        "total_amount": 250.0,
        "line_items": [{"description": "Software license", "amount": 250.0}],
        "gst": None,
        "payment_mode": "card",
    },
    # EUR, no rate printed → per-currency default lookup ("EUR:90").
    "expense_eur_no_rate": {
        "doc_type": "expense",
        "vendor_name": "Initech GmbH",
        "date": "2026-04-06",
        "currency": "EUR",
        "fx_rate": None,
        "total_amount": 200.0,
        "line_items": [{"description": "Hosting", "amount": 200.0}],
        "gst": None,
        "payment_mode": "bank",
    },
    # INR regression — currency INR, fx_rate null. Must behave exactly as today.
    "expense_inr": {
        "doc_type": "expense",
        "vendor_name": "Uber",
        "date": "2026-04-04",
        "currency": "INR",
        "fx_rate": None,
        "total_amount": 500.0,
        "line_items": [{"description": "Ride", "amount": 500.0}],
        "gst": None,
        "payment_mode": "upi",
    },
    # USD + GST breakdown. total 118 = 100 base + 9 CGST + 9 SGST (all USD).
    # GST-leg scaling asserted at builder level (see module docstring note).
    "expense_usd_with_gst": {
        "doc_type": "expense",
        "vendor_name": "Stark Industries",
        "date": "2026-04-07",
        "currency": "USD",
        "fx_rate": 80.0,
        "total_amount": 118.0,
        "line_items": [{"description": "Parts", "amount": 100.0}],
        "gst": {
            "cgst_rate": 9.0,
            "cgst_amount": 9.0,
            "sgst_rate": 9.0,
            "sgst_amount": 9.0,
            "igst_rate": None,
            "igst_amount": None,
            "gstin": "27AAACS1234A1Z5",
        },
        "payment_mode": "bank",
    },
}


def vision_payload(name: str) -> dict:
    """Return a deep-ish copy of the raw Vision-response dict for ``name``."""
    src = FX_DOCUMENTS[name]
    return json.loads(json.dumps(src))


def vision_json(name: str) -> str:
    """Return the fixture as the JSON string Claude Vision would emit."""
    return json.dumps(FX_DOCUMENTS[name])


def vision_message(name: str) -> MagicMock:
    """Return a MagicMock matching the Anthropic messages.create response.

    Mirrors the ``_mock_vision_message`` helpers in the upload tests: the
    message's ``content[0].text`` is the Vision JSON string.
    """
    msg = MagicMock()
    msg.content = [MagicMock(text=vision_json(name))]
    return msg


def extracted(name: str) -> ExtractedDocument:
    """Return the fixture parsed into an ``ExtractedDocument`` (builder input)."""
    return parse_vision_response(vision_json(name))
