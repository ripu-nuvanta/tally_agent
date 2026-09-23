import pytest

from v2.probes.companies import COMPANIES
from v2.probes.setup.company_b import CompanyBLoadError, load_company_b
from v2.probes.setup.company_b_data import generate
from v2.probes.setup.writes import TallyWriter, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, sync_client
from v2.tests.probes.fakes import ScriptedIO

B = COMPANIES["B"]


def _loader(books, **io_kwargs):
    said: list[str] = []
    writer = TallyWriter(sync_client(books.transport()), said.append)
    return writer, ScriptedIO(**io_kwargs), said


def _empty_b():
    books = FakeBooks(name=B)
    books.state["voucherTypes"] = ["Sales", "Purchase", "Receipt", "Payment", "Sales - GST"]
    return books


def test_a_first_load_lists_before_creating_and_reads_back_every_write():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    ds = generate()
    assert report.created["groups"] == len(ds.groups)
    assert report.created["vouchers"] == len(ds.vouchers)
    assert report.problems == []
    # the first request for each type is a read, not an import
    first = books.requests[0]
    assert "<TALLYREQUEST>Import Data</TALLYREQUEST>" not in first


def test_a_second_load_sends_zero_creates():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    before = len([r for r in books.requests if "Import Data" in r])
    report = load_company_b(writer, io)
    after = len([r for r in books.requests if "Import Data" in r])
    assert after == before                       # nothing new was sent
    assert sum(report.created.values()) == 0
    assert report.skipped["vouchers"] == 960


def test_a_master_that_already_exists_is_not_recreated():
    books = _empty_b()
    books.state["groups"]["National Creditors"] = {"parent": "Sundry Creditors"}
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert report.skipped["groups"] == 1
    creates = [r for r in books.requests if 'GROUP NAME="National Creditors" ACTION="Create"' in r]
    assert creates == []                         # LESSONS §15 rule 10


def test_a_company_without_probe_in_the_name_is_refused_before_any_request():
    books = FakeBooks(name="Sharma & Sons Traders")
    writer, io, _ = _loader(books)
    with pytest.raises(WriteRefused):
        load_company_b(writer, io, company="Sharma & Sons Traders")
    assert books.requests == []


def test_a_missing_custom_voucher_type_pauses_and_then_fails_if_still_missing():
    books = _empty_b()
    books.state["voucherTypes"] = ["Sales", "Purchase", "Receipt", "Payment"]   # no "Sales - GST"
    writer, io, _ = _loader(books)
    with pytest.raises(CompanyBLoadError, match="Sales - GST"):
        load_company_b(writer, io)
    assert any("Sales - GST" in w for w in io.waits)         # the operator was asked first


def test_a_flag_that_did_not_stick_becomes_a_pause_naming_the_voucher():
    books = _empty_b()
    books.drop_flags = True                      # the fake accepts the voucher but not ISOPTIONAL/ISCANCELLED
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert any("[S0-B:201]" in p for p in report.pauses)
    assert any("[S0-B:301]" in p for p in report.pauses)


def test_the_run_ends_by_checking_counts_and_balances_against_the_expected_figures():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert report.problems == []


def test_a_wrong_count_is_reported_as_a_problem_not_swallowed():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    books.state["vouchers"].popitem()             # something vanished behind our back (dict keyed by master id)
    report = load_company_b(writer, io)
    assert any("2025-26" in p or "count" in p.lower() for p in report.problems)


def test_educational_mode_only_uses_dates_tally_accepts():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io, licence="educational")
    dates = [v["date"] for v in books.state["vouchers"].values()]
    assert all(int(d[6:8]) in (1, 2, 31) for d in dates)
