"""Unit tests — voucher_action dispatches by voucher_type (Group B, Task 8).

The /chat/voucher-action endpoint must call the correct TallyWriter method for
each voucher_type, passing party_ledger / contra ledger / bill_ref / gst as
appropriate, and preserve the existing Payment path + the FX no-rate guard.
The writer methods are mocked; we assert which method got called and with what.
"""
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "FILE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    monkeypatch.setattr(settings, "JWT_SECRET", None)
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    from backend.main import app
    with TestClient(app) as tc:
        yield tc


_SUCCESS = {"success": True, "last_vch_id": "42", "created": 1}


def _post(client, entry, action="approve"):
    return client.post(
        "/api/chat/voucher-action",
        json={"action": action, "entry": entry, "company": "Test Co",
              "session_id": "s"},
    )


def test_payment_dispatch_calls_create_payment_voucher(client):
    entry = {
        "id": "p1", "voucher_type": "Payment", "date": "20260404",
        "debit_ledger": "Travel Expenses", "credit_ledger": "Cash",
        "amount": 500.0, "narration": "Uber", "gst_entries": [],
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_payment_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_written"
    m.assert_awaited_once()
    assert m.await_args.kwargs["debit_ledger"] == "Travel Expenses"


def test_purchase_dispatch_calls_purchase_writer(client):
    entry = {
        "id": "pu1", "voucher_type": "Purchase", "date": "20260210",
        "debit_ledger": "Purchase Accounts", "credit_ledger": "Croma Electronics",
        "party_ledger": "Croma Electronics", "amount": 15340.0,
        "narration": "Croma purchase", "gst_entries": [],
        "bill_reference": "CRO-5678", "bill_type": "New Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher_ledger",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert "purchase" in resp.json()["message"].lower()
    m.assert_awaited_once()
    kw = m.await_args.kwargs
    assert kw["party_ledger"] == "Croma Electronics"
    assert kw["purchase_ledger"] == "Purchase Accounts"
    assert kw["bill_ref"] == "CRO-5678"


def test_sales_dispatch_calls_sales_writer(client):
    entry = {
        "id": "sa1", "voucher_type": "Sales", "date": "20260301",
        "debit_ledger": "Infosys Ltd", "credit_ledger": "Sales Accounts",
        "party_ledger": "Infosys Ltd", "amount": 118000.0,
        "narration": "Sale", "gst_entries": [],
        "bill_reference": "INV-1", "bill_type": "New Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_sales_voucher_ledger",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert "sales" in resp.json()["message"].lower()
    m.assert_awaited_once()
    kw = m.await_args.kwargs
    assert kw["party_ledger"] == "Infosys Ltd"
    assert kw["sales_ledger"] == "Sales Accounts"


def test_debit_note_dispatch_calls_create_debit_note(client):
    # Correct DN convention (live test 2026-06-09): party on DEBIT, purchase-
    # returns contra on CREDIT. chat.py dispatches purchase_ledger=credit_ledger.
    entry = {
        "id": "dn1", "voucher_type": "Debit Note", "date": "20260305",
        "debit_ledger": "Croma Electronics", "credit_ledger": "Purchase Returns",
        "party_ledger": "Croma Electronics", "amount": 4718.0,
        "narration": "Return", "gst_entries": [],
        "bill_reference": "CRO-5678", "bill_type": "Agst Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_debit_note",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert "debit note" in resp.json()["message"].lower()
    m.assert_awaited_once()
    kw = m.await_args.kwargs
    assert kw["party_ledger"] == "Croma Electronics"
    assert kw["purchase_ledger"] == "Purchase Returns"
    assert kw["party_ledger"] != kw["purchase_ledger"]
    assert kw["bill_ref"] == "CRO-5678"


def test_credit_note_dispatch_calls_create_credit_note(client):
    # Correct CN convention (live test 2026-06-09): party on CREDIT, sales-
    # returns contra on DEBIT. chat.py dispatches sales_ledger=debit_ledger.
    entry = {
        "id": "cn1", "voucher_type": "Credit Note", "date": "20260315",
        "debit_ledger": "Sales Returns", "credit_ledger": "Infosys Ltd",
        "party_ledger": "Infosys Ltd", "amount": 11800.0,
        "narration": "Discount CN", "gst_entries": [],
        "bill_reference": "INV-FEB-001", "bill_type": "Agst Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_credit_note",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert "credit note" in resp.json()["message"].lower()
    m.assert_awaited_once()
    kw = m.await_args.kwargs
    assert kw["party_ledger"] == "Infosys Ltd"
    assert kw["sales_ledger"] == "Sales Returns"
    assert kw["party_ledger"] != kw["sales_ledger"]
    assert kw["bill_ref"] == "INV-FEB-001"


def test_debit_note_edit_form_mapping_keeps_legs_distinct(client):
    """Contract guard: an edit-form DN entry (party on DEBIT, purchase-returns on
    CREDIT — the correct return polarity) must dispatch with the party as
    party_ledger and the CONTRA (credit_ledger) as purchase_ledger, kept distinct.
    """
    entry = {
        "id": "dn2", "voucher_type": "Debit Note", "date": "20260305",
        # correct edit-form convention: debit = party, credit = returns ledger
        "debit_ledger": "Croma Electronics", "credit_ledger": "Purchase Returns",
        "party_ledger": "Croma Electronics", "amount": 4718.0,
        "narration": "Return", "gst_entries": [],
        "bill_reference": "CRO-5678", "bill_type": "Agst Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_debit_note",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    kw = m.await_args.kwargs
    assert kw["purchase_ledger"] == "Purchase Returns"
    assert kw["party_ledger"] == "Croma Electronics"
    assert kw["purchase_ledger"] != kw["party_ledger"]


def test_credit_note_edit_form_mapping_keeps_legs_distinct(client):
    """Contract guard: an edit-form CN entry (party on CREDIT, sales-returns on
    DEBIT — the correct return polarity) must dispatch with the party as
    party_ledger and the CONTRA (debit_ledger) as sales_ledger, kept distinct.
    """
    entry = {
        "id": "cn2", "voucher_type": "Credit Note", "date": "20260315",
        # correct edit-form convention: debit = returns ledger, credit = party
        "debit_ledger": "Sales Returns", "credit_ledger": "Infosys Ltd",
        "party_ledger": "Infosys Ltd", "amount": 11800.0,
        "narration": "Discount CN", "gst_entries": [],
        "bill_reference": "INV-FEB-001", "bill_type": "Agst Ref",
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_credit_note",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    kw = m.await_args.kwargs
    assert kw["sales_ledger"] == "Sales Returns"
    assert kw["party_ledger"] == "Infosys Ltd"
    assert kw["sales_ledger"] != kw["party_ledger"]


def test_default_voucher_type_is_payment(client):
    """Legacy entries without voucher_type still write a Payment (regression)."""
    entry = {
        "id": "x", "date": "20260404", "debit_ledger": "Travel", "credit_ledger": "Cash",
        "amount": 500.0, "narration": "n", "gst_entries": [],
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_payment_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    m.assert_awaited_once()


@pytest.mark.parametrize(
    "voucher_type,writer_method",
    [
        ("Purchase", "create_purchase_voucher_ledger"),
        ("Sales", "create_sales_voucher_ledger"),
        ("Debit Note", "create_debit_note"),
        ("Credit Note", "create_credit_note"),
    ],
)
def test_empty_party_ledger_blocks_party_voucher(client, voucher_type, writer_method):
    """Finding 3: a party voucher with empty/missing party_ledger must return a
    voucher_error and NOT call the writer.
    """
    entry = {
        "id": "np1", "voucher_type": voucher_type, "date": "20260301",
        "debit_ledger": "Purchase Accounts", "credit_ledger": "Sales Accounts",
        "party_ledger": "", "amount": 1000.0, "narration": "n", "gst_entries": [],
    }
    with patch(
        f"backend.tally_bridge.writer.TallyWriter.{writer_method}",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_error"
    assert "party ledger" in resp.json()["message"].lower()
    m.assert_not_awaited()


def test_valid_party_ledger_still_writes(client):
    """Finding 3 happy path: a Purchase WITH a party_ledger still writes."""
    entry = {
        "id": "ok1", "voucher_type": "Purchase", "date": "20260301",
        "debit_ledger": "Purchase Accounts", "credit_ledger": "Acme",
        "party_ledger": "Acme", "amount": 1000.0, "narration": "n", "gst_entries": [],
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher_ledger",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_written"
    m.assert_awaited_once()


def test_fx_no_rate_guard_blocks_foreign_write(client):
    """Foreign-currency entry with no rate must NOT call any writer."""
    entry = {
        "id": "fx", "voucher_type": "Purchase", "date": "20260301",
        "debit_ledger": "Purchase Accounts", "credit_ledger": "Acme",
        "party_ledger": "Acme", "amount": 0.0, "narration": "n",
        "gst_entries": [], "original_currency": "USD", "fx_rate": 0.0,
    }
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher_ledger",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_error"
    m.assert_not_awaited()
