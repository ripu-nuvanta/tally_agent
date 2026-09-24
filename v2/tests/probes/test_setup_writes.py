import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.setup.import_xml import ImportResult, wrap_import
from v2.probes.setup.writes import TallyWriter, WriteFailed, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, import_result, sync_client
from v2.tests.probes.fakes import FakeTally, objects_xml

A = COMPANIES["A"]
B = COMPANIES["B"]


def _writer(books):
    said: list[str] = []
    return TallyWriter(sync_client(books.transport()), said.append), said


def _imports(books):
    return [r for r in books.requests if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in r]


def test_import_result_parses_the_live_response_shape():
    result = ImportResult.parse(import_result(created=1, last_vch_id="51"))
    assert (result.created, result.altered, result.deleted, result.errors, result.last_vch_id) == (1, 0, 0, 0, "51")
    assert result.clean
    assert not ImportResult.parse(import_result(errors=1, line_error="Voucher not found")).clean


def test_copied_import_envelope_escapes_and_checks_the_report():
    root = ET.fromstring(wrap_import("All Masters", "Sharma & Sons' Probe Traders", "<LEDGER/>"))
    assert root.find(".//SVCURRENTCOMPANY").text == "Sharma & Sons' Probe Traders"
    with pytest.raises(ValueError):
        wrap_import("Everything", A, "<LEDGER/>")


def test_payment_create_alter_delete_round_trip():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    master_id = writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-throwaway 1")
    assert master_id == "51" and books.state["alt_vch"] == 51
    writer.alter_voucher_narration(A, master_id, "S0-throwaway 1 (altered)")
    assert books.state["vouchers"]["51"]["narration"] == "S0-throwaway 1 (altered)"
    writer.delete_voucher(A, master_id)
    assert books.state["vouchers"] == {} and books.state["alt_vch"] == 55


def test_payment_uses_the_verified_voucher_shape():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    writer.delete_voucher(A, writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-t"))
    create, delete = _imports(books)
    for fragment in ("<ALLLEDGERENTRIES.LIST>", "<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>",
                     "<DATE>20260331</DATE>", "<AMOUNT>-1.00</AMOUNT>", "<AMOUNT>1.00</AMOUNT>",
                     "<LEDGERNAME>Cash</LEDGERNAME>", "<REPORTNAME>Vouchers</REPORTNAME>"):
        assert fragment in create
    assert 'DATE="31-Mar-2026"' in delete and 'TAGNAME="Master ID" TAGVALUE="51"' in delete


def test_post_dated_payment_sends_the_flag_and_logs_the_read_back():
    books = FakeBooks(name=A)
    writer, said = _writer(books)
    writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-pd", post_dated=True)
    assert "<ISPOSTDATED>Yes</ISPOSTDATED>" in _imports(books)[0]
    assert books.state["vouchers"]["51"]["post_dated"] == "Yes"
    assert any("read-back IsPostDated" in line for line in said)


def test_post_dated_create_missing_from_the_readback_still_returns_the_master_id():
    """I3: a post-dated voucher can be created (Tally confirms LASTVCHID) but not show up in the Voucher collection
    read-back yet — that must not raise, and the operator can still delete it by the Master ID."""
    fake = FakeTally([A])

    def import_handler(body):
        return import_result(deleted=1, last_vch_id="99") if 'ACTION="Delete"' in body else \
            import_result(created=1, last_vch_id="99")

    fake.route("<TALLYREQUEST>Import Data</TALLYREQUEST>", import_handler)
    fake.route("S0OpVouchers", lambda body: objects_xml("VOUCHER", []))    # the voucher never shows up on read-back
    said: list[str] = []
    writer = TallyWriter(sync_client(fake.transport()), said.append)

    master_id = writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-pd-missing",
                                      post_dated=True)
    assert master_id == "99"
    assert any("post-dated voucher created (LASTVCHID 99) but not listed in the Voucher collection" in line
              for line in said)

    writer.delete_voucher(A, master_id)   # doesn't raise "still there": the read-back never shows it either way


def test_non_post_dated_create_missing_from_the_readback_still_raises():
    """The I3 relaxation is only for post_dated=True; an ordinary create with no read-back proof still fails."""
    fake = FakeTally([A])
    fake.route("<TALLYREQUEST>Import Data</TALLYREQUEST>", lambda body: import_result(created=1, last_vch_id="99"))
    fake.route("S0OpVouchers", lambda body: objects_xml("VOUCHER", []))
    writer = TallyWriter(sync_client(fake.transport()), lambda line: None)
    with pytest.raises(WriteFailed, match="not found on read-back"):
        writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-missing")


def test_writes_to_a_company_without_probe_are_refused_before_sending():
    books = FakeBooks(name="Bharat Traders Private Limited")
    writer, _ = _writer(books)
    before = len(books.requests)
    with pytest.raises(WriteRefused):
        writer.create_payment("Bharat Traders Private Limited", ledger="Electricity", amount=Decimal("1"),
                              narration="S0-x")
    with pytest.raises(WriteRefused):
        writer.delete_ledger("Bharat Traders Private Limited", "Cash")
    assert len(books.requests) == before


def test_seed_rename_is_the_only_exception():
    books = FakeBooks(name=SEED_COMPANY)
    writer, _ = _writer(books)
    with pytest.raises(WriteRefused):
        writer.rename_company(SEED_COMPANY, "Bharat Traders Copy")
    writer.rename_company(SEED_COMPANY, A)
    assert books.companies() == [A]
    assert "<COMPANY NAME=\"Bharat Traders Private Limited\" ACTION=\"Alter\"><NAME>" in _imports(books)[0]


def test_an_empty_value_alter_is_refused():
    writer, _ = _writer(FakeBooks(name=A))
    with pytest.raises(ValueError):
        writer.alter_ledger_email(A, "Electricity", "")


def test_ledger_create_alter_delete_and_rename():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    writer.create_ledger(A, "S0 Probe Ledger", "Indirect Expenses")
    writer.alter_ledger_email(A, "S0 Probe Ledger", "s0probe-1@example.com")
    assert books.state["ledgers"]["S0 Probe Ledger"]["email"] == "s0probe-1@example.com"
    writer.delete_ledger(A, "S0 Probe Ledger")
    assert "S0 Probe Ledger" not in books.state["ledgers"]
    writer.rename_ledger(A, "Rajesh Computers", "Rajesh Computers S0")
    writer.rename_ledger(A, "Rajesh Computers S0", "Rajesh Computers")
    assert "Rajesh Computers" in books.state["ledgers"]
    assert books.state["alt_mst"] == 266 + 5


def test_duplicate_ledger_create_is_refused_before_sending():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    with pytest.raises(WriteFailed, match="already exists"):
        writer.create_ledger(A, "Electricity", "Indirect Expenses")
    assert _imports(books) == []
    assert not books.popup


def test_altered_1_without_the_change_fails_the_write():
    fake = FakeTally([A])
    fake.route("<TALLYREQUEST>Import Data</TALLYREQUEST>", lambda body: import_result(altered=1))
    fake.route("S0OpLedger", lambda body: objects_xml("LEDGER", [
        {"Name": "S0 Probe Ledger", "Parent": "Indirect Expenses", "Email": "", "AlterID": "1"}]))
    writer = TallyWriter(sync_client(fake.transport()), lambda line: None)
    with pytest.raises(WriteFailed, match="not proof"):
        writer.alter_ledger_email(A, "S0 Probe Ledger", "s0probe-1@example.com")


def test_duplicate_stock_group_raises_the_popup():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    assert writer.raise_duplicate_master_popup(A) == "timeout"
    assert books.popup
    with pytest.raises(WriteFailed):
        writer.company_names()


def test_licence_info_reads_mode_and_release():
    writer, _ = _writer(FakeBooks(name=A))
    info = writer.licence_info()
    assert info.educational is True and info.release == "7.0"
    assert _writer(FakeBooks(name=A, educational=False))[0].licence_info().educational is False


# --- master writers (company B) -------------------------------------------------------------------------------------

def test_creating_a_group_then_listing_it_round_trips():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_group(B, "National Creditors", "Sundry Creditors")
    assert writer.list_groups(B)["National Creditors"] == "Sundry Creditors"


def test_create_group_lists_before_creating_and_reads_back():
    books = FakeBooks(name=B)
    writer, said = _writer(books)
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    assert writer.list_groups(B)["Local Creditors"] == "Sundry Creditors"
    assert len(_imports(books)) == 1


def test_a_second_create_sends_nothing():
    books = FakeBooks(name=B)
    writer, said = _writer(books)
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    assert len(_imports(books)) == 1                      # the second call never reached Tally
    assert any("already exists" in line for line in said)


def test_a_simple_unit_has_no_name_attribute_and_is_marked_simple():
    """Op 1 (live-verified, docs/tally-write-exploration-v4.md:35-39): no NAME attribute, ISSIMPLEUNIT=Yes."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_unit(B, "Nos")
    sent = _imports(books)[-1]
    assert '<UNIT ACTION="Create">' in sent
    assert 'NAME="Nos"' not in sent
    assert "<ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>" in sent


def test_a_compound_unit_carries_its_base_and_conversion():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_unit(B, "Nos")
    writer.create_unit(B, "Box of 10 Nos", base="Nos", conversion=10)
    sent = _imports(books)[-1]
    assert "<BASEUNITS>Nos</BASEUNITS>" in sent and "<CONVERSION>10</CONVERSION>" in sent
    assert "<ISSIMPLEUNIT>No</ISSIMPLEUNIT>" in sent


def test_a_stock_item_without_an_hsn_is_created_gst_not_applicable():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_stock_item(B, "Whiteboard Marker", unit="Nos")
    sent = _imports(books)[-1]
    assert "<GSTAPPLICABLE>Not Applicable</GSTAPPLICABLE>" in sent    # LESSONS §15 r12
    assert "HSNCODE" not in sent


def test_a_stock_item_with_an_hsn_carries_both_the_top_level_and_the_nested_copy():
    """Op 3 gotcha (docs/tally-write-exploration-v4.md:98): HSNCODE/HSN are duplicated at top level and inside
    HSNDETAILS.LIST — both are needed."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_stock_item(B, "Monitor 24in", unit="Nos", hsn="8528")
    sent = _imports(books)[-1]
    assert "<GSTAPPLICABLE>Applicable</GSTAPPLICABLE>" in sent
    assert "<GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>" in sent
    assert "<HSNCODE>8528</HSNCODE>\n  <HSN>8528</HSN>" in sent            # top-level copy
    assert "<HSNDETAILS.LIST><HSNCODE>8528</HSNCODE></HSNDETAILS.LIST>" in sent    # nested copy


def test_a_stock_item_with_an_opening_balance_carries_qty_rate_and_value():
    """Op 3 shapes (docs/tally-write-exploration-v4.md:90-92): OPENINGBALANCE/OPENINGRATE carry the unit name;
    the rate and value are money (2dp), the quantity is not."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_stock_item(B, "Monitor 24in", unit="TstN",
                             opening_qty=Decimal("5"), opening_rate=Decimal("11000"))
    sent = _imports(books)[-1]
    assert "<OPENINGBALANCE>5 TstN</OPENINGBALANCE>" in sent
    assert "<OPENINGRATE>11000.00/TstN</OPENINGRATE>" in sent
    assert "<OPENINGVALUE>55000.00</OPENINGVALUE>" in sent


def test_a_party_ledger_carries_bill_wise_and_a_valid_gstin():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Pune Traders", parent="Local Creditors", bill_wise=True,
                               gstin="27AAAPL1234C1ZV")
    sent = _imports(books)[-1]
    assert "<ISBILLWISEON>Yes</ISBILLWISEON>" in sent
    assert "<PARTYGSTIN>27AAAPL1234C1ZV</PARTYGSTIN>" in sent


def test_a_negative_dataset_opening_is_sent_signed_on_the_wire():
    """C30 (overturns C21/F11): Tally reads OPENINGBALANCE's sign — negative = Dr, positive = Cr — it does NOT
    infer the side from the parent group. Live evidence: backend/tally_bridge/import_builder.py's abs() landed
    company A's HDFC −5,00,000 / SBI −2,00,000 as CREDITS (v2/tests/fixtures/sync/p18_A_ledger_list.xml shows them
    positive, like Capital Account). So the dataset's debit-negative value goes on the wire as is."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Kolhapur Retail Mart", parent="Sundry Debtors", bill_wise=False,
                               opening=Decimal("-45000.00"))
    sent = _imports(books)[-1]
    assert "<OPENINGBALANCE>-45000.00</OPENINGBALANCE>" in sent


def test_a_positive_dataset_opening_is_sent_as_a_positive_credit():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Capital Account", parent="Capital Account", bill_wise=False,
                               opening=Decimal("1000000.00"))
    assert "<OPENINGBALANCE>1000000.00</OPENINGBALANCE>" in _imports(books)[-1]


def _tb_row(books, group):
    return next(row for row in books._trial_balance_rows(books.state) if row[0] == group)


def test_a_debit_opening_lands_on_the_debit_side_of_the_fake_trial_balance():
    """The fake must read the wire sign the way Tally does (negative = Dr), so the balance tests mean something."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Kolhapur Retail Mart", parent="Sundry Debtors", bill_wise=False,
                               opening=Decimal("-45000.00"))
    assert _tb_row(books, "Sundry Debtors")[1:] == ("-45000.00", "")


def test_the_fake_reads_the_wire_sign_not_the_parent_groups_nature():
    """A positive OPENINGBALANCE under a debit-nature group (an overdraft under Bank Accounts) is a CREDIT in
    Tally — the fake must not re-sign it from the group (the disproven Op 5 / C21 rule)."""
    books = FakeBooks(name=B)
    xml = wrap_import("All Masters", B, '<LEDGER NAME="HDFC OD" ACTION="Create">\n  <NAME.LIST><NAME>HDFC OD</NAME>'
                      '</NAME.LIST>\n  <PARENT>Bank Accounts</PARENT>\n  <OPENINGBALANCE>25000.00</OPENINGBALANCE>'
                      '\n</LEDGER>')
    sync_client(books.transport()).post("/", content=xml.encode("utf-8"))
    assert _tb_row(books, "Bank Accounts")[1:] == ("", "25000.00")


@pytest.mark.parametrize("name, parent, opening, match", [
    ("HDFC OD A/c", "Bank Accounts", Decimal("25000.00"), "contra-natural"),     # a CREDIT under a debit group
    ("Advance from Kolhapur", "Sundry Debtors", Decimal("1000.00"), "contra-natural"),  # a debtor in credit
    ("Drawings", "Capital Account", Decimal("-5000.00"), "contra-natural"),      # a DEBIT under a credit group
    ("Pune Traders", "Local Creditors", Decimal("1.00"), "nature is unknown"),   # m3: natural credit, custom group
])
def test_a_contra_natural_or_unclassifiable_opening_is_refused_before_anything_is_sent(name, parent, opening, match):
    """M1, kept as a DATASET sanity check after C30: the wire is now signed, so a contra-natural opening would
    land where its sign says — but in this dataset one is far likelier a sign slip than a real overdraft, so it is
    still refused, as is an opening under a group whose nature this module cannot name. m3: each case matches
    its own branch's message, so the custom-group case cannot pass via the contra-natural branch."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    with pytest.raises(ValueError, match=match):
        writer.create_party_ledger(B, name, parent=parent, bill_wise=False, opening=opening)
    assert books.requests == []


@pytest.mark.parametrize("opening", [Decimal("-18000.00"), Decimal("18000.00")])
def test_a_duties_and_taxes_opening_may_sit_on_either_side(opening):
    """m1: an Input GST ledger carries a DEBIT opening (ITC carried forward), Output GST a credit — both normal."""
    from v2.probes.setup.writes import check_opening_side

    check_opening_side("Input CGST", "Duties & Taxes", opening)


def test_every_company_b_opening_matches_its_parent_groups_nature():
    """M1: the loader's own dataset must never trip the contra-natural refusal."""
    from v2.probes.setup.company_b_data import generate
    from v2.probes.setup.writes import check_opening_side

    for ledger in generate().ledgers:
        if ledger.opening is not None:
            check_opening_side(ledger.name, ledger.parent, ledger.opening)


def test_the_non_billwise_debtor_is_written_bill_wise_off():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Kolhapur Retail Mart", parent="Sundry Debtors", bill_wise=False)
    assert "<ISBILLWISEON>No</ISBILLWISEON>" in _imports(books)[-1]


def test_a_write_to_a_company_without_probe_in_the_name_is_refused():
    books = FakeBooks(name="Sharma & Sons Traders")
    writer, _ = _writer(books)
    with pytest.raises(WriteRefused):
        writer.create_group("Sharma & Sons Traders", "Local Creditors", "Sundry Creditors")
    assert _imports(books) == []


def test_a_sales_voucher_uses_the_verified_sign_convention():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Sales", date="20230601", narration="[S0-B:7] sale", party="Pune Traders",
        lines=[("Pune Traders", Decimal("-11800.00"), True), ("Sales", Decimal("10000.00"), False),
               ("Output CGST", Decimal("900.00"), False), ("Output SGST", Decimal("900.00"), False)],
        inventory=[("A4 Paper", "Nos", Decimal("10"), Decimal("1000.00"), Decimal("10000.00"))],
        bills=[("B/7", "New Ref", Decimal("-11800.00"), "30 Days")])
    sent = _imports(books)[-1]
    assert "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" in sent          # party
    assert "<AMOUNT>-11800.00</AMOUNT>" in sent
    assert "<ALLINVENTORYENTRIES.LIST>" in sent                         # r15: goods via the stock grid
    assert "<BILLCREDITPERIOD>30 Days</BILLCREDITPERIOD>" in sent
    # F1 fix: invoice-mode (Sales/Purchase) uses the unprefixed tag, verified by Op 6 + import_builder.py, never the
    # ALL-prefixed one — match the opening bracket so this can't be satisfied by a substring of ALLLEDGERENTRIES.LIST.
    assert "<LEDGERENTRIES.LIST>" in sent
    assert "<ALLLEDGERENTRIES.LIST>" not in sent
    assert "<RATE>1000.00/Nos</RATE>" in sent
    assert "<ACTUALQTY>10 Nos</ACTUALQTY>" in sent
    # I1's sibling half: Op 6 goods out — ISDEEMEDPOSITIVE=No against a POSITIVE amount, on the inventory row
    # and its ACCOUNTINGALLOCATIONS child alike.
    inventory_block = sent.split("<ALLINVENTORYENTRIES.LIST>")[1].split("</ALLINVENTORYENTRIES.LIST>")[0]
    assert inventory_block.count("<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>") == 2
    assert "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" not in inventory_block
    assert inventory_block.count("<AMOUNT>10000.00</AMOUNT>") == 2


def test_a_purchase_inverts_the_signs():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Purchase", date="20230601", narration="[S0-B:9] buy", party="Mumbai Supplies",
        lines=[("Mumbai Supplies", Decimal("5900.00"), False), ("Purchase", Decimal("-5000.00"), True),
               ("Input CGST", Decimal("-450.00"), True), ("Input SGST", Decimal("-450.00"), True)])
    sent = _imports(books)[-1]
    assert "<LEDGERENTRIES.LIST>" in sent
    assert "<ALLLEDGERENTRIES.LIST>" not in sent
    party_block = sent.split("<LEDGERENTRIES.LIST>")[1]
    assert "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>" in party_block
    assert "<AMOUNT>5900.00</AMOUNT>" in party_block


def test_a_receipt_still_uses_all_ledger_entries():
    """Pins the split from the other side: non-invoice vch_types (Op 8/9, create_payment) keep the ALL-prefixed tag."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Receipt", date="20230601", narration="[S0-B:50] receipt", party="Pune Traders",
        lines=[("Cash", Decimal("-1000.00"), True), ("Pune Traders", Decimal("1000.00"), False)])
    sent = _imports(books)[-1]
    assert "<ALLLEDGERENTRIES.LIST>" in sent
    # M3: this fixture used to be the MIRROR of Op 8 (cash No/+, party Yes/-). Nothing here asserted signs, so
    # it passed — while encoding the wrong convention as a fixture. Op 8's own line: "Cash debit (Yes/-),
    # party credit (No/+)" (docs/tally-write-exploration-v4.md).
    cash_block = sent.split("<ALLLEDGERENTRIES.LIST>")[1]
    assert "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" in cash_block and "<AMOUNT>-1000.00</AMOUNT>" in cash_block
    assert "<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>" in sent
    assert "<ISINVOICE>" not in sent


def test_a_custom_purchase_subtype_carrying_inventory_is_accepted():
    """F6: 'Purchase - GST' is parented to Purchase, exactly analogous to the dataset's 'Sales - GST' — the
    inventory-placement guard must accept it (not just is_invoice_type's ledger-tag choice) and emit invoice-mode
    XML, matching the sibling Sales-prefixed case.

    I1 (final review): this test used to assert only that `<ALLINVENTORYENTRIES.LIST>` was PRESENT, so it passed
    while the block inside carried ISDEEMEDPOSITIVE=No against a negative AMOUNT — the mismatched permutation Op
    7 records as EXCEPTIONS=1 (the deemed flag was decided by `vch_type == "Purchase"`, exact equality, while the
    ledger tag three lines above used `startswith`). The flag inside the block is now asserted."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Purchase - GST", date="20230601", narration="[S0-B:60] buy", party="Mumbai Supplies",
        lines=[("Mumbai Supplies", Decimal("1180.00"), False), ("Purchase", Decimal("-1000.00"), True),
               ("Input CGST", Decimal("-90.00"), True), ("Input SGST", Decimal("-90.00"), True)],
        inventory=[("A4 Paper", "Nos", Decimal("1"), Decimal("1000.00"), Decimal("-1000.00"))])
    sent = _imports(books)[-1]
    assert "<LEDGERENTRIES.LIST>" in sent
    assert "<ALLLEDGERENTRIES.LIST>" not in sent
    assert "<ISINVOICE>Yes</ISINVOICE>" in sent
    assert "<ALLINVENTORYENTRIES.LIST>" in sent
    inventory_block = sent.split("<ALLINVENTORYENTRIES.LIST>")[1].split("</ALLINVENTORYENTRIES.LIST>")[0]
    # Op 7: goods in — ISDEEMEDPOSITIVE=Yes against a NEGATIVE amount, on the inventory row AND on its
    # ACCOUNTINGALLOCATIONS child (both flags come from the same expression, so both are pinned here).
    assert inventory_block.count("<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>") == 2
    assert "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>" not in inventory_block
    assert inventory_block.count("<AMOUNT>-1000.00</AMOUNT>") == 2


def test_inventory_without_a_second_line_is_refused_before_anything_is_sent():
    """F7: `lines` needs a party line and a nominal ledger line for the ACCOUNTINGALLOCATIONS.LIST convention to
    be meaningful at all — a single-line `lines` with inventory is refused rather than silently misallocating."""
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    with pytest.raises(ValueError, match="nominal ledger"):
        writer.create_b_voucher(
            B, vch_type="Sales", date="20230601", narration="[S0-B:61] x", party="P",
            lines=[("P", Decimal("0.00"), True)],
            inventory=[("A4 Paper", "Nos", Decimal("1"), Decimal("0.00"), Decimal("0.00"))])
    assert _imports(books) == []


def test_an_unbalanced_voucher_is_refused_before_anything_is_sent():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    with pytest.raises(ValueError, match="does not balance"):
        writer.create_b_voucher(B, vch_type="Sales", date="20230601", narration="[S0-B:1] x", party="P",
                                lines=[("P", Decimal("-100.00"), True), ("Sales", Decimal("90.00"), False)])
    assert _imports(books) == []

