"""FakeBooks: GROUP / UNIT / STOCKITEM masters, the S0B* read-back collections, voucher types, and the two
opt-in failure modes (drop_flags, fail_imports) that Tasks 6-7 need. Talks straight to the transport with
wrap_import / wrap_collection — no TallyWriter methods here (Task 4 supplies create_group etc.)."""
from __future__ import annotations

import httpx
import pytest

from v2.agent.tally.envelopes import wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.setup.import_xml import ImportResult, esc, wrap_import
from v2.tests.probes.fake_books import FakeBooks, sync_client

B = "Sharma & Sons' Probe Traders"


def _post(books: FakeBooks, xml: str) -> str:
    return sync_client(books.transport()).post("/", content=xml, timeout=5).text


def _create(tag: str, name: str, inner: str) -> str:
    return wrap_import("All Masters", B, f'<{tag} NAME="{esc(name)}" ACTION="Create">{inner}</{tag}>')


def _group_xml(name: str, parent: str) -> str:
    return _create("GROUP", name, f'<NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST><PARENT>{esc(parent)}</PARENT>')


def _unit_xml(name: str) -> str:
    return _create("UNIT", name, f'<NAME>{esc(name)}</NAME>')


def _item_xml(name: str, parent: str, base_units: str) -> str:
    return _create("STOCKITEM", name,
                    f'<NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST><PARENT>{esc(parent)}</PARENT>'
                    f'<BASEUNITS>{esc(base_units)}</BASEUNITS>')


def _list(books: FakeBooks, collection: str, object_type: str, fields: list[str]) -> list[dict[str, str]]:
    xml = wrap_collection(collection, object_type, fields, B)
    return read_objects(_post(books, xml), object_type, fields)


# --- GROUP -----------------------------------------------------------------------------------------------------
def test_creating_a_group_then_listing_it_round_trips():
    books = FakeBooks(name=B)
    result = ImportResult.parse(_post(books, _group_xml("National Creditors", "Sundry Creditors")))
    assert result.created == 1 and result.clean

    rows = _list(books, "S0BGroups", "Group", ["Name", "Parent"])
    assert {"Name": "National Creditors", "Parent": "Sundry Creditors"} in rows


def test_a_duplicate_group_create_raises_the_modal():
    books = FakeBooks(name=B)
    _post(books, _group_xml("National Creditors", "Sundry Creditors"))
    with pytest.raises(httpx.ReadTimeout):
        _post(books, _group_xml("National Creditors", "Sundry Creditors"))


# --- UNIT --------------------------------------------------------------------------------------------------------
def test_creating_a_unit_then_listing_it_round_trips():
    books = FakeBooks(name=B)
    result = ImportResult.parse(_post(books, _unit_xml("Nos")))
    assert result.created == 1 and result.clean

    rows = _list(books, "S0BUnits", "Unit", ["Name"])
    assert {"Name": "Nos"} in rows


def test_a_duplicate_unit_create_raises_the_modal():
    books = FakeBooks(name=B)
    _post(books, _unit_xml("Nos"))
    with pytest.raises(httpx.ReadTimeout):
        # straight to the transport: the writer's own list-before-create guard is Task 4's job
        sync_client(books.transport()).post("/", content=_unit_xml("Nos"), timeout=5)


# --- STOCKITEM -------------------------------------------------------------------------------------------------
def test_creating_a_stock_item_then_listing_it_round_trips():
    books = FakeBooks(name=B)
    result = ImportResult.parse(_post(books, _item_xml("Widget", "Electronics", "Nos")))
    assert result.created == 1 and result.clean

    rows = _list(books, "S0BItems", "StockItem", ["Name", "Parent", "BaseUnits"])
    assert {"Name": "Widget", "Parent": "Electronics", "BaseUnits": "Nos"} in rows


def test_a_duplicate_stock_item_create_raises_the_modal():
    books = FakeBooks(name=B)
    _post(books, _item_xml("Widget", "Electronics", "Nos"))
    with pytest.raises(httpx.ReadTimeout):
        _post(books, _item_xml("Widget", "Electronics", "Nos"))


# --- S0BLedgers / S0BVouchers reuse the existing ledger/voucher state ---------------------------------------------
def test_s0b_ledgers_returns_the_seeded_ledgers():
    books = FakeBooks(name=B)
    rows = _list(books, "S0BLedgers", "Ledger", ["Name", "Parent"])
    assert {"Name": "Cash", "Parent": "Cash-in-Hand"} in rows


def test_s0b_vouchers_returns_a_created_voucher():
    books = FakeBooks(name=B)
    inner = ('<VOUCHER VCHTYPE="Payment" ACTION="Create"><DATE>1-Apr-25</DATE>'
             "<NARRATION>Rent</NARRATION><VOUCHERTYPENAME>Payment</VOUCHERTYPENAME></VOUCHER>")
    ImportResult.parse(_post(books, wrap_import("Vouchers", B, inner)))

    rows = _list(books, "S0BVouchers", "Voucher", ["MasterId", "Narration"])
    assert {"MasterId": "51", "Narration": "Rent"} in rows


# --- voucher types -----------------------------------------------------------------------------------------------
def test_voucher_types_are_seeded_and_listable():
    books = FakeBooks(name=B)
    rows = _list(books, "S0BVoucherTypes", "VoucherType", ["Name"])
    names = {row["Name"] for row in rows}
    assert names == {"Sales", "Purchase", "Receipt", "Payment", "Contra", "Journal"}


# --- drop_flags ---------------------------------------------------------------------------------------------------
def test_drop_flags_discards_iscancelled_and_isoptional_on_readback():
    books = FakeBooks(name=B, drop_flags=True)
    inner = ('<VOUCHER VCHTYPE="Payment" ACTION="Create"><DATE>1-Apr-25</DATE>'
             "<NARRATION>Rent</NARRATION><VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>"
             "<ISCANCELLED>Yes</ISCANCELLED><ISOPTIONAL>Yes</ISOPTIONAL></VOUCHER>")
    result = ImportResult.parse(_post(books, wrap_import("Vouchers", B, inner)))
    assert result.created == 1 and result.clean          # the import itself still "succeeds"

    rows = _list(books, "S0BVouchers", "Voucher", ["MasterId", "IsCancelled", "IsOptional"])
    row = next(r for r in rows if r["MasterId"] == "51")
    assert row["IsCancelled"] == "No"
    assert row["IsOptional"] == "No"


def test_without_drop_flags_iscancelled_sticks():
    books = FakeBooks(name=B)
    inner = ('<VOUCHER VCHTYPE="Payment" ACTION="Create"><DATE>1-Apr-25</DATE>'
             "<NARRATION>Rent</NARRATION><VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>"
             "<ISCANCELLED>Yes</ISCANCELLED></VOUCHER>")
    ImportResult.parse(_post(books, wrap_import("Vouchers", B, inner)))

    rows = _list(books, "S0BVouchers", "Voucher", ["MasterId", "IsCancelled"])
    row = next(r for r in rows if r["MasterId"] == "51")
    assert row["IsCancelled"] == "Yes"


# --- fail_imports --------------------------------------------------------------------------------------------------
def test_fail_imports_fails_every_import():
    books = FakeBooks(name=B, fail_imports=True)
    result = ImportResult.parse(_post(books, _group_xml("National Creditors", "Sundry Creditors")))
    assert result.created == 0
    assert result.errors == 1
    assert result.line_error == "fake import failure"

    # nothing was actually stored
    assert _list(books, "S0BGroups", "Group", ["Name"]) == []
