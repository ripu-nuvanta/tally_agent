"""Unit tests — inventory write path must NOT CREATE masters that already exist.

Root cause (confirmed live): sending create_unit / create_stock_group /
create_stock_item for a master that ALREADY EXISTS makes this Tally instance pop
a blocking modal that freezes the HTTP gateway. The fix: fetch existing stock
items once (list_stock_items), derive the set of known item names / units /
groups, and only call a create for genuinely-missing masters.

These tests patch list_stock_items so the "existing" inventory is deterministic,
and assert the EXACT writer.create_* calls made.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.tally_bridge.models import StockItem


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

# Existing inventory: item "A4 Paper Ream 500 sheets" in group "Stationery",
# base unit "Nos". So {a4 paper..} is a known item, {nos} a known unit,
# {stationery} a known group.
_EXISTING = [
    StockItem(name="A4 Paper Ream 500 sheets", parent_group="Stationery", base_units="Nos"),
    StockItem(name="HP Laptop 15s", parent_group="Electronics", base_units="Nos"),
]


def _post(client, entry, action="approve"):
    return client.post(
        "/api/chat/voucher-action",
        json={"action": action, "entry": entry, "company": "Test Co",
              "session_id": "s"},
    )


def _patch_existing():
    return patch(
        "backend.tally_bridge.queries.masters.list_stock_items",
        new=AsyncMock(return_value=list(_EXISTING)),
    )


def _base_entry(line_items):
    return {
        "id": "inv1", "voucher_type": "Purchase", "date": "20260210",
        "debit_ledger": "Purchase Accounts", "credit_ledger": "Croma Electronics",
        "party_ledger": "Croma Electronics", "amount": 70210.0,
        "narration": "Goods purchase",
        "gst_entries": [
            {"ledger": "CGST Input", "amount": 5355.0},
            {"ledger": "SGST Input", "amount": 5355.0},
        ],
        "bill_reference": "CRO-9001", "bill_type": "New Ref",
        "reference": "CRO-9001", "reference_date": "20260210",
        "is_inventory": True,
        "line_items": line_items,
    }


def test_matched_line_creates_no_masters(client):
    """A matched line (matched_item set / item exists) creates NOTHING."""
    entry = _base_entry([
        {"description": "A4 Paper Ream 500 sheets", "qty": 10.0, "rate": 500.0,
         "unit": "Nos", "gst_rate": 18.0,
         "matched_item": "A4 Paper Ream 500 sheets", "create_new": False,
         "stock_name": "A4 Paper Ream 500 sheets", "stock_group": "Stationery",
         "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_unit, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_group, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_written"
    m_unit.assert_not_awaited()
    m_group.assert_not_awaited()
    m_item.assert_not_awaited()
    m_vch.assert_awaited_once()


def test_create_new_line_with_known_unit_and_group_creates_only_item(client):
    """A create-new line whose unit ('Nos') AND group ('Stationery') already
    exist among existing items creates ONLY the stock item — no create_unit and
    no create_stock_group."""
    entry = _base_entry([
        {"description": "Brother Toner Cartridge", "qty": 5.0, "rate": 10900.0,
         "unit": "nos", "gst_rate": 18.0,  # lowercase — casefold must still match
         "matched_item": None, "create_new": True,
         "stock_name": "Brother Toner Cartridge", "stock_group": "STATIONERY",
         "hsn": "8443", "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_unit, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_group, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    m_unit.assert_not_awaited()
    m_group.assert_not_awaited()
    m_item.assert_awaited_once()
    m_vch.assert_awaited_once()


def test_create_new_line_with_brand_new_unit_and_group_creates_all_three(client):
    """A create-new line with a brand-new unit AND group creates all three."""
    entry = _base_entry([
        {"description": "Steel Rod 12mm", "qty": 3.0, "rate": 200.0,
         "unit": "Kg", "gst_rate": 18.0,
         "matched_item": None, "create_new": True,
         "stock_name": "Steel Rod 12mm", "stock_group": "Hardware",
         "hsn": "7214", "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_unit, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_group, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    m_unit.assert_awaited_once()
    assert m_unit.await_args.args[0] == "Kg" or m_unit.await_args.kwargs.get("name") == "Kg"
    m_group.assert_awaited_once()
    m_item.assert_awaited_once()
    m_vch.assert_awaited_once()


def test_create_new_line_with_existing_item_name_is_not_recreated(client):
    """A create-new line whose stock_name already exists is NOT re-created
    (even if create_new flag is set)."""
    entry = _base_entry([
        {"description": "A4 Paper Ream 500 sheets", "qty": 7.0, "rate": 480.0,
         "unit": "Nos", "gst_rate": 18.0,
         "matched_item": None, "create_new": True,  # flag says new, but it exists
         "stock_name": "a4 paper ream 500 sheets",  # casefold match to existing
         "stock_group": "Stationery", "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_unit, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_group, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    m_unit.assert_not_awaited()
    m_group.assert_not_awaited()
    m_item.assert_not_awaited()
    m_vch.assert_awaited_once()


def test_duplicate_new_lines_within_voucher_create_once(client):
    """Two create-new lines sharing a brand-new unit+group create that unit and
    group only ONCE (in-memory known-sets updated as we go)."""
    entry = _base_entry([
        {"description": "Steel Rod 12mm", "qty": 3.0, "rate": 200.0,
         "unit": "Kg", "gst_rate": 18.0, "matched_item": None, "create_new": True,
         "stock_name": "Steel Rod 12mm", "stock_group": "Hardware",
         "ledger": "Purchase Accounts"},
        {"description": "Steel Rod 16mm", "qty": 2.0, "rate": 300.0,
         "unit": "Kg", "gst_rate": 18.0, "matched_item": None, "create_new": True,
         "stock_name": "Steel Rod 16mm", "stock_group": "Hardware",
         "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_unit, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_group, patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert m_unit.await_count == 1
    assert m_group.await_count == 1
    assert m_item.await_count == 2
    m_vch.assert_awaited_once()


def test_master_create_timeout_returns_voucher_error_not_hang(client):
    """If a master-create call raises (e.g. transport timeout / would-be modal),
    it must propagate to a clean voucher_error rather than hang."""
    entry = _base_entry([
        {"description": "Steel Rod 12mm", "qty": 3.0, "rate": 200.0,
         "unit": "Kg", "gst_rate": 18.0, "matched_item": None, "create_new": True,
         "stock_name": "Steel Rod 12mm", "stock_group": "Hardware",
         "ledger": "Purchase Accounts"},
    ])
    with _patch_existing(), patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(side_effect=TimeoutError("gateway froze")),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch:
        resp = _post(client, entry)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["type"] == "voucher_error"
    m_vch.assert_not_awaited()
