import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.setup.import_xml import ImportResult, wrap_import
from v2.probes.setup.writes import TallyWriter, WriteFailed, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, import_result, sync_client
from v2.tests.probes.fakes import FakeTally, objects_xml

A = COMPANIES["A"]


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
