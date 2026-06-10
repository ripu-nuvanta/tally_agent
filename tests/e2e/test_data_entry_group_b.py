"""E2E tests — Group B voucher-type pipeline (mock Tally + mock Claude, legacy mode).

These exercise the FULL upload → classify → review → write pipeline for every
Group B voucher type through the real FastAPI routes and the built-in mock Tally
handler (NO live Tally, NO real Claude API). Only the Claude Vision call is
mocked — via ``vision_docs.vision_message(<fixture>)`` reusing the on-disk
``tests/fixtures/vision/*.json`` fixtures — so the routing, ledger lookup,
party-voucher fetch (for DN/CN), and write dispatch all run for real against the
mock handler.

DB-row verification (UploadedFile / VoucherEntry audit trail) lives in the
DB-gated companion ``tests/e2e/test_db_data_entry_group_b.py``.

Matrix covered here (design § E2E + Integration tables):
  - Purchase invoice (INR)  → classify purchase → party + purchase ledger → write
  - Purchase (USD)          → FX extraction → INR shown → write with INR
  - Sales invoice (INR)     → classify sales → party + sales ledger → write
  - Debit Note (INR)        → against-invoice options fetched (real mock) → write
  - Credit Note (INR)       → classify CN → write
  - DN (no party match)     → empty against-invoice options → manual ref → write
  - Reclassify/edit         → Vision says payment, user edits voucher_type → write
  - Regression: payment/expense (B1a) upload → write still works end-to-end
"""
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import vision_docs

_FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    # Legacy (non-DB) mode so auth is a no-op even if .env has DATABASE_URL set.
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    monkeypatch.setattr(settings, "JWT_SECRET", None)
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    from backend.main import app
    with TestClient(app) as tc:
        yield tc


def _upload(client, fixture_name, message="data entry"):
    """Upload a fake image whose Vision response is the given fixture."""
    with patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_docs.vision_message(fixture_name)),
    ):
        return client.post(
            "/api/chat/upload",
            files={"file": ("doc.jpg", io.BytesIO(_FAKE_JPEG), "image/jpeg")},
            data={"message": message},
        )


def _write(client, entry, session_id="grpb"):
    """Approve (write) a review-card entry through /chat/voucher-action."""
    return client.post(
        "/api/chat/voucher-action",
        json={
            "action": "approve",
            "entry": entry,
            "company": "Test Co",
            "session_id": session_id,
        },
    )


def _entry_for_write(review_entry, **overrides):
    """Build the voucher-action payload from a review-card entry.

    Carries through the Group B fields the write dispatch needs (voucher_type,
    party_ledger, bill_reference, gst_entries, is_new_ledger, ...).
    """
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
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Purchase (INR)
# ---------------------------------------------------------------------------

class TestPurchasePipeline:
    def test_purchase_inr_upload_classify_write(self, client):
        """Upload purchase invoice → routed to Purchase → party (creditor) +
        purchase ledger + GST → write succeeds."""
        up = _upload(client, "purchase_service_inr", "purchase invoice")
        assert up.status_code == 200, up.text
        data = up.json()
        assert data["data"]["type"] == "voucher_review"
        entry = data["data"]["entries"][0]

        assert entry["voucher_type"] == "Purchase"
        assert entry["is_party_ledger"] is True
        # party is the credit side of a purchase (Sundry Creditor)
        assert entry["party_ledger"] == "Croma Electronics"
        assert entry["credit_ledger"] == "Croma Electronics"
        assert entry["debit_ledger"]  # purchase account
        assert entry["amount"] == 15340.0

        w = _write(client, _entry_for_write(entry), "purchase-inr")
        assert w.status_code == 200, w.text
        body = w.json()
        assert body["data"]["type"] == "voucher_written"
        assert "successfully" in body["message"].lower()

    def test_purchase_usd_fx_then_write_inr(self, client):
        """USD purchase → FX extraction → INR amount on the card → write with INR."""
        up = _upload(client, "purchase_saas_usd", "saas invoice")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Purchase"
        assert entry["original_currency"] == "USD"
        assert entry["original_amount"] == 1730.0
        assert entry["fx_rate"] == 83.46
        # amount on the card is the INR-converted value, not the USD original.
        assert entry["amount"] != entry["original_amount"]
        assert abs(entry["amount"] - 1730.0 * 83.46) < 1.0
        assert "FX:" in entry["narration"]

        w = _write(client, _entry_for_write(entry), "purchase-usd")
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"


# ---------------------------------------------------------------------------
# Sales (INR)
# ---------------------------------------------------------------------------

class TestSalesPipeline:
    def test_sales_inr_upload_classify_write(self, client):
        """Upload sales invoice → routed to Sales → party (debtor) + sales
        ledger → write succeeds."""
        up = _upload(client, "sales_service_inr", "sales invoice")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Sales"
        assert entry["is_party_ledger"] is True
        # party is the debit side of a sale (Sundry Debtor)
        assert entry["party_ledger"] == "Infosys Ltd"
        assert entry["debit_ledger"] == "Infosys Ltd"
        assert entry["credit_ledger"]  # sales account
        assert entry["amount"] == 118000.0

        w = _write(client, _entry_for_write(entry), "sales-inr")
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"


# ---------------------------------------------------------------------------
# Debit Note (INR) — against-invoice options fetched from the REAL mock handler
# ---------------------------------------------------------------------------

class TestDebitNotePipeline:
    def test_debit_note_fetches_against_invoice_then_write(self, client):
        """DN for Croma Electronics → the mock party-voucher handler returns a
        prior Purchase invoice → against-invoice options are surfaced → write."""
        up = _upload(client, "debit_note_return_inr", "debit note")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Debit Note"
        assert entry["is_party_ledger"] is True
        assert entry["party_ledger"] == "Croma Electronics"
        assert entry["bill_type"] == "Agst Ref"
        # bill_reference comes from the document's original_invoice_ref.
        assert entry["bill_reference"] == "CRO-2026-5678"
        # The mock handler seeds Croma with one prior Purchase voucher; the
        # orchestrator must have fetched it (real path, not mocked).
        assert entry["party_vouchers"], "expected party vouchers fetched from mock"
        assert entry["against_invoice_options"]
        opt = entry["against_invoice_options"][0]
        assert opt["voucher_number"] or opt["reference"]

        # Select that ref explicitly (simulating the user choosing it) and write.
        ref = entry["against_invoice_options"][0]["reference"]
        w = _write(client, _entry_for_write(entry, bill_reference=ref), "dn-inr")
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"

    def test_debit_note_no_party_match_manual_ref_write(self, client):
        """DN for a party with no prior vouchers → empty against-invoice options
        → user supplies a manual ref → write still succeeds."""
        up = _upload(client, "debit_note_no_ref", "debit note no ref")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Debit Note"
        # "Unknown Supplier" is not in the mock party-voucher map → empty list.
        assert entry["party_vouchers"] == []
        assert entry["against_invoice_options"] == []

        # Manual ref fallback (New Ref) — supply our own reference.
        w = _write(
            client,
            _entry_for_write(entry, bill_reference="MANUAL-DN-001"),
            "dn-manual",
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"


# ---------------------------------------------------------------------------
# Credit Note (INR)
# ---------------------------------------------------------------------------

class TestCreditNotePipeline:
    def test_credit_note_upload_classify_write(self, client):
        """Upload credit note → routed to Credit Note → party (debtor) + sales
        ledger → write succeeds."""
        up = _upload(client, "credit_note_return_inr", "credit note")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Credit Note"
        assert entry["is_party_ledger"] is True
        assert entry["party_ledger"] == "Infosys Ltd"
        assert entry["bill_type"] == "Agst Ref"
        assert entry["bill_reference"] == "INV-2026-FEB-001"

        w = _write(client, _entry_for_write(entry), "cn-inr")
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"


# ---------------------------------------------------------------------------
# Reclassify / edit: Vision says payment, user edits to a different type
# ---------------------------------------------------------------------------

class TestReclassifyPipeline:
    def test_vision_payment_reclassified_to_purchase_writes(self, client):
        """Vision extracts a Payment/expense; the user edits the entry into a
        Purchase (adds a party ledger) before writing. The write dispatch must
        honour the edited voucher_type, not the originally-classified one."""
        up = _upload(client, "payment_with_gst_inr", "petty expense")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]
        assert entry["voucher_type"] == "Payment"

        # User reclassifies in the edit form → Purchase against a party ledger.
        edited = _entry_for_write(
            entry,
            voucher_type="Purchase",
            party_ledger="Croma Electronics",
            credit_ledger="Croma Electronics",
            debit_ledger="Purchase - Office Supplies",
            bill_reference="EDIT-REF-1",
            # is_new_ledger off — purchase account + party both treated as existing
            is_new_ledger=False,
        )
        w = client.post(
            "/api/chat/voucher-action",
            json={
                "action": "edit",
                "entry": edited,
                "company": "Test Co",
                "session_id": "reclassify",
            },
        )
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"


# ---------------------------------------------------------------------------
# Regression: original B1a payment/expense path still works end-to-end
# ---------------------------------------------------------------------------

class TestPaymentRegression:
    def test_payment_expense_upload_write_regression(self, client):
        """The original Set B1a flow (expense → Payment voucher) must still work
        unchanged after Group B."""
        up = _upload(client, "payment_petty_cash_inr", "cab fare")
        assert up.status_code == 200, up.text
        entry = up.json()["data"]["entries"][0]

        assert entry["voucher_type"] == "Payment"
        assert entry["is_party_ledger"] is False
        assert entry.get("party_ledger") is None

        w = _write(client, _entry_for_write(entry), "payment-regression")
        assert w.status_code == 200, w.text
        assert w.json()["data"]["type"] == "voucher_written"
