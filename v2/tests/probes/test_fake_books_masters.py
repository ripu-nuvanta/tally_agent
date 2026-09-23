"""FakeBooks: GROUP / UNIT / STOCKITEM masters, the S0B* read-back collections, voucher types, and the two
opt-in failure modes (drop_flags, fail_imports) that Tasks 6-7 need. Talks straight to the transport with
wrap_import / wrap_collection — no TallyWriter methods here (Task 4 supplies create_group etc.)."""
from __future__ import annotations

import httpx
import pytest

from v2.agent.tally.envelopes import wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.setup.import_xml import ImportResult, esc, wrap_import
from decimal import Decimal

from v2.tests.probes.fake_books import FakeBooks, deemed_positive_matches, sync_client

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


# --- I5: the fake sees ISDEEMEDPOSITIVE, and rejects a flag that disagrees with its amount sign ----------------------
def _voucher_xml(entries: str, inventory: str = "") -> str:
    return ('<VOUCHER VCHTYPE="Receipt" ACTION="Create"><DATE>1-Apr-25</DATE>'
            "<NARRATION>[S0-B:1] x</NARRATION><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>"
            f"{entries}{inventory}</VOUCHER>")


def _entry(ledger: str, flag: str, amount: str) -> str:
    return (f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{esc(ledger)}</LEDGERNAME>"
            f"<ISDEEMEDPOSITIVE>{flag}</ISDEEMEDPOSITIVE><AMOUNT>{amount}</AMOUNT></ALLLEDGERENTRIES.LIST>")


def test_the_fake_stores_isdeemedpositive_on_every_line():
    """I5: the fake used to compute balances from `line["amount"]` alone and never stored the flag, so the one
    field whose wrong value is the documented cause of EXCEPTIONS=1 was invisible to every assertion."""
    books = FakeBooks(name=B)
    _post(books, wrap_import("Vouchers", B, _voucher_xml(
        _entry("Cash", "Yes", "-1000.00") + _entry("Pune Traders", "No", "1000.00"))))
    lines = books.state["vouchers"]["51"]["lines"]
    assert [(l["ledger"], l["deemed_positive"], l["amount"]) for l in lines] == [
        ("Cash", "Yes", "-1000.00"), ("Pune Traders", "No", "1000.00")]


def test_the_fake_rejects_a_line_whose_flag_disagrees_with_its_amount_sign():
    """Op 6/7/8: Yes always carries a NEGATIVE amount, No a POSITIVE one. Every other permutation the live
    exploration tried answered EXCEPTIONS=1 with no LINEERROR (v4 doc, cross-cutting finding 2) — the fake now
    approximates that acceptance rule instead of echoing whatever it is handed."""
    books = FakeBooks(name=B)
    result = ImportResult.parse(_post(books, wrap_import("Vouchers", B, _voucher_xml(
        _entry("Cash", "No", "-1000.00") + _entry("Pune Traders", "Yes", "1000.00")))))
    assert result.exceptions == 1 and result.created == 0 and not result.clean
    assert books.state["vouchers"] == {}          # and nothing was stored


def test_the_fake_checks_the_inventory_row_and_its_accounting_allocation_too():
    """Where Task 6's I1 defect actually lived: the ledger lines were right and the ALLINVENTORYENTRIES block
    carried No against a negative amount."""
    books = FakeBooks(name=B)
    inventory = ('<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>A4 Paper</STOCKITEMNAME>'
                 "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>-1000.00</AMOUNT>"
                 "<ACCOUNTINGALLOCATIONS.LIST><LEDGERNAME>Purchase</LEDGERNAME>"
                 "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-1000.00</AMOUNT>"
                 "</ACCOUNTINGALLOCATIONS.LIST></ALLINVENTORYENTRIES.LIST>")
    result = ImportResult.parse(_post(books, wrap_import("Vouchers", B, _voucher_xml(
        _entry("Mumbai Supplies", "No", "1180.00") + _entry("Input CGST", "Yes", "-180.00"), inventory))))
    assert result.exceptions == 1 and books.state["vouchers"] == {}


def test_a_zero_amount_pins_no_side_and_is_accepted_either_way():
    assert deemed_positive_matches("Yes", Decimal("0.00"))
    assert deemed_positive_matches("No", Decimal("0.00"))
    assert deemed_positive_matches("Yes", Decimal("-1.00")) and not deemed_positive_matches("Yes", Decimal("1.00"))
    assert deemed_positive_matches("No", Decimal("1.00")) and not deemed_positive_matches("No", Decimal("-1.00"))
