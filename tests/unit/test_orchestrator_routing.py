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

# Ledgers the mock Tally "returns" — covers party groups + contra ledgers +
# the six seed-company GST ledgers under Duties & Taxes.
_LEDGERS = [
    {"name": "Croma Electronics", "parent_group": "Sundry Creditors"},
    {"name": "Infosys Ltd", "parent_group": "Sundry Debtors"},
    {"name": "Anthropic PBC", "parent_group": "Sundry Creditors"},
    {"name": "Purchase Accounts", "parent_group": "Purchase Accounts"},
    {"name": "Sales Accounts", "parent_group": "Sales Accounts"},
    {"name": "HDFC Bank", "parent_group": "Bank Accounts"},
    {"name": "Cash", "parent_group": "Cash-in-hand"},
    {"name": "Office Supplies", "parent_group": "Indirect Expenses"},
    {"name": "CGST Input", "parent_group": "Duties & Taxes"},
    {"name": "SGST Input", "parent_group": "Duties & Taxes"},
    {"name": "IGST Input", "parent_group": "Duties & Taxes"},
    {"name": "CGST Output", "parent_group": "Duties & Taxes"},
    {"name": "SGST Output", "parent_group": "Duties & Taxes"},
    {"name": "IGST Output", "parent_group": "Duties & Taxes"},
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


from backend.tally_bridge.models import StockItem

# Stock items the company already has (used by inventory goods detection).
_STOCK_ITEMS = [
    StockItem(name="A4 Paper Ream 500 sheets", parent_group="Primary", base_units="Nos"),
    StockItem(name="HP Laptop 15s", parent_group="Primary", base_units="Nos"),
    StockItem(name="Logitech Wireless Mouse", parent_group="Primary", base_units="Nos"),
]


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
        "backend.services.stock_resolver.list_stock_items",
        new=AsyncMock(return_value=_STOCK_ITEMS),
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


def _gst_ledger_names(entry):
    return {e["ledger"] for e in entry.get("gst_entries", [])}


@pytest.mark.asyncio
async def test_purchase_gets_input_gst_legs():
    """Intrastate purchase resolves Input CGST/SGST from Duties & Taxes."""
    result = await _run_upload("purchase_office_inr")
    entry = _entry(result)
    assert _gst_ledger_names(entry) == {"CGST Input", "SGST Input"}
    # Contra (purchase) leg posts the BASE; party gross = base + GST.
    gst_total = sum(e["amount"] for e in entry["gst_entries"])
    assert abs((entry["amount"] - gst_total) - (15340.0 - 2342.0)) < 0.01


@pytest.mark.asyncio
async def test_interstate_purchase_gets_input_igst():
    result = await _run_upload("purchase_interstate_inr")
    entry = _entry(result)
    assert _gst_ledger_names(entry) == {"IGST Input"}


@pytest.mark.asyncio
async def test_sales_gets_output_gst_legs():
    result = await _run_upload("sales_service_inr")
    entry = _entry(result)
    assert _gst_ledger_names(entry) == {"CGST Output", "SGST Output"}


@pytest.mark.asyncio
async def test_debit_note_gets_input_gst_legs():
    sample = [
        {"voucher_number": "CRO-2026-5678", "date": "2026-02-10",
         "voucher_type": "Purchase", "amount": 15340.0, "reference": "CRO-2026-5678"},
    ]
    result = await _run_upload("debit_note_return_inr", party_vouchers=sample)
    entry = _entry(result)
    assert _gst_ledger_names(entry) == {"CGST Input", "SGST Input"}


@pytest.mark.asyncio
async def test_credit_note_gets_output_gst_legs():
    sample = [
        {"voucher_number": "INV-001", "date": "2026-03-01",
         "voucher_type": "Sales", "amount": 118000.0, "reference": "INV-001"},
    ]
    result = await _run_upload("credit_note_return_inr", party_vouchers=sample)
    entry = _entry(result)
    assert _gst_ledger_names(entry) == {"CGST Output", "SGST Output"}


@pytest.mark.asyncio
async def test_missing_gst_ledger_warns_no_leg():
    """When the needed GST ledger isn't in the ledger list, warn and omit the leg."""
    orch = Orchestrator()
    session = SessionContext(session_id="s1")
    no_gst_ledgers = [
        {"name": "Croma Electronics", "parent_group": "Sundry Creditors"},
        {"name": "Purchase Accounts", "parent_group": "Purchase Accounts"},
    ]
    with _temp_file() as path, patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_docs.vision_message("purchase_office_inr")),
    ), patch(
        "backend.tally_bridge.response_parser.parse_ledger_list",
        return_value=no_gst_ledgers,
    ):
        result = await orch.process_file_upload(
            file_path=path, filename="doc.jpg", mime_type="image/jpeg",
            user_message="entry", client=_FakeClient(), session=session,
            file_id="file-1",
        )
    entry = result["data"]["entries"][0]
    assert entry["gst_entries"] == []
    assert any("not found" in w for w in entry["warnings"])


@pytest.mark.asyncio
async def test_goods_purchase_is_inventory_with_line_items():
    """A purchase with quantity-bearing lines → inventory path."""
    result = await _run_upload("purchase_goods_inr")
    entry = _entry(result)
    assert entry["voucher_type"] == "Purchase"
    assert entry["is_inventory"] is True
    assert len(entry["line_items"]) == 2
    # First line matches a seeded item, second is new.
    by_desc = {li["description"]: li for li in entry["line_items"]}
    assert by_desc["A4 Paper Ream 500 sheets"]["matched_item"] == "A4 Paper Ream 500 sheets"
    assert by_desc["A4 Paper Ream 500 sheets"]["create_new"] is False
    assert by_desc["Brother Toner Cartridge TN-2380"]["create_new"] is True
    # Per-line ledger defaults to the chosen purchase contra ledger.
    assert by_desc["A4 Paper Ream 500 sheets"]["ledger"] == "Purchase Accounts"
    assert "A4 Paper Ream 500 sheets" in entry["available_stock_items"]
    assert entry["default_stock_group"] == "AI Imported Items"


@pytest.mark.asyncio
async def test_goods_sales_is_inventory_with_line_items():
    result = await _run_upload("sales_goods_inr")
    entry = _entry(result)
    assert entry["voucher_type"] == "Sales"
    assert entry["is_inventory"] is True
    assert len(entry["line_items"]) == 2
    by_desc = {li["description"]: li for li in entry["line_items"]}
    assert by_desc["HP Laptop 15s"]["matched_item"] == "HP Laptop 15s"
    # Per-line ledger defaults to the chosen sales contra ledger.
    assert by_desc["HP Laptop 15s"]["ledger"] == "Sales Accounts"


@pytest.mark.asyncio
async def test_services_purchase_stays_accounting_only():
    """A purchase whose lines have no quantity → accounting-only (no inventory)."""
    result = await _run_upload("purchase_saas_usd")
    entry = _entry(result)
    assert entry.get("is_inventory") in (False, None)
    assert entry.get("line_items") in (None, [])


@pytest.mark.asyncio
async def test_services_sales_stays_accounting_only():
    result = await _run_upload("sales_service_inr")
    entry = _entry(result)
    assert entry.get("is_inventory") in (False, None)


@pytest.mark.asyncio
async def test_payment_never_inventory():
    result = await _run_upload("payment_petty_cash_inr")
    entry = _entry(result)
    assert entry.get("is_inventory") in (False, None)


@pytest.mark.asyncio
async def test_fx_fields_present_on_foreign_purchase():
    result = await _run_upload("purchase_saas_usd")
    entry = _entry(result)
    assert entry["voucher_type"] == "Purchase"
    assert entry["original_currency"] == "USD"
    assert entry["fx_rate"] is not None
    assert entry["amount"] != entry["original_amount"]
