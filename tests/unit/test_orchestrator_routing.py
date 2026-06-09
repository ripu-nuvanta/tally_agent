"""Unit tests — orchestrator routes file uploads by doc_type (Group B, Task 9).

Each doc_type must select the correct voucher builder, the correct ledgers
(party under Sundry Creditors/Debtors + contra ledger), and produce a review
entry carrying the Group B fields (voucher_type, party_ledger, is_party_ledger,
bill_reference, party_vouchers/against_invoice_options, FX fields).

The Vision call and the Tally ledger fetch are mocked; routing is pure logic.
"""
import os
import tempfile
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from backend.agents.context import SessionContext
from backend.agents.orchestrator import Orchestrator
from tests.fixtures import vision_docs

# Ledgers the mock Tally "returns" — covers party groups + contra ledgers.
_LEDGERS = [
    {"name": "Croma Electronics", "parent_group": "Sundry Creditors"},
    {"name": "Infosys Ltd", "parent_group": "Sundry Debtors"},
    {"name": "Anthropic PBC", "parent_group": "Sundry Creditors"},
    {"name": "Purchase Accounts", "parent_group": "Purchase Accounts"},
    {"name": "Sales Accounts", "parent_group": "Sales Accounts"},
    {"name": "HDFC Bank", "parent_group": "Bank Accounts"},
    {"name": "Cash", "parent_group": "Cash-in-hand"},
    {"name": "Office Supplies", "parent_group": "Indirect Expenses"},
]


class _FakeClient:
    async def post_xml(self, xml):
        return "<LEDGERS/>"


@contextmanager
def _temp_file():
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.write(fd, b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    os.close(fd)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)


async def _run_upload(fixture_name, party_vouchers=None):
    """Drive process_file_upload for a fixture; return the result dict."""
    orch = Orchestrator()
    session = SessionContext(session_id="s1")
    with _temp_file() as path, patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_docs.vision_message(fixture_name)),
    ), patch(
        "backend.tally_bridge.response_parser.parse_ledger_list",
        return_value=_LEDGERS,
    ), patch(
        "backend.tally_bridge.queries.vouchers.get_party_vouchers",
        new=AsyncMock(return_value=party_vouchers or []),
    ):
        result = await orch.process_file_upload(
            file_path=path,
            filename="doc.jpg",
            mime_type="image/jpeg",
            user_message="entry",
            client=_FakeClient(),
            session=session,
            file_id="file-1",
        )
    assert result["data"] is not None, result["message"]
    return result


def _entry(result):
    return result["data"]["entries"][0]


@pytest.mark.asyncio
async def test_payment_routes_to_payment_builder():
    result = await _run_upload("payment_petty_cash_inr")
    entry = _entry(result)
    assert entry["voucher_type"] == "Payment"
    assert entry["is_party_ledger"] is False
    assert entry.get("party_ledger") is None
    assert "available_payment_ledgers" in result["data"]


@pytest.mark.asyncio
async def test_purchase_routes_to_purchase_builder():
    result = await _run_upload("purchase_office_inr")
    entry = _entry(result)
    assert entry["voucher_type"] == "Purchase"
    assert entry["is_party_ledger"] is True
    assert entry["party_ledger"] == "Croma Electronics"
    assert entry["credit_ledger"] == "Croma Electronics"
    assert entry["bill_type"] == "New Ref"


@pytest.mark.asyncio
async def test_sales_routes_to_sales_builder():
    result = await _run_upload("sales_service_inr")
    entry = _entry(result)
    assert entry["voucher_type"] == "Sales"
    assert entry["is_party_ledger"] is True
    assert entry["party_ledger"] == "Infosys Ltd"
    assert entry["debit_ledger"] == "Infosys Ltd"
    assert entry["bill_type"] == "New Ref"


@pytest.mark.asyncio
async def test_debit_note_routes_with_against_invoice_options():
    sample = [
        {"voucher_number": "CRO-2026-5678", "date": "2026-02-10",
         "voucher_type": "Purchase", "amount": 15340.0, "reference": "CRO-2026-5678"},
    ]
    result = await _run_upload("debit_note_return_inr", party_vouchers=sample)
    entry = _entry(result)
    assert entry["voucher_type"] == "Debit Note"
    assert entry["is_party_ledger"] is True
    assert entry["bill_type"] == "Agst Ref"
    assert entry["bill_reference"] == "CRO-2026-5678"
    assert entry["against_invoice_options"]
    assert entry["party_vouchers"] == sample


@pytest.mark.asyncio
async def test_credit_note_routes_with_against_invoice_options():
    sample = [
        {"voucher_number": "INV-001", "date": "2026-03-01",
         "voucher_type": "Sales", "amount": 118000.0, "reference": "INV-001"},
    ]
    result = await _run_upload("credit_note_return_inr", party_vouchers=sample)
    entry = _entry(result)
    assert entry["voucher_type"] == "Credit Note"
    assert entry["bill_type"] == "Agst Ref"
    assert entry["party_vouchers"] == sample
    assert entry["against_invoice_options"]


@pytest.mark.asyncio
async def test_fx_fields_present_on_foreign_purchase():
    result = await _run_upload("purchase_saas_usd")
    entry = _entry(result)
    assert entry["voucher_type"] == "Purchase"
    assert entry["original_currency"] == "USD"
    assert entry["fx_rate"] is not None
    assert entry["amount"] != entry["original_amount"]
