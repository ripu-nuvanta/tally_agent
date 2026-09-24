"""sign_check.py — the one-request-pair live check that settles C30 (signed OPENINGBALANCE), run offline here."""
import httpx
import pytest

from v2.probes.companies import COMPANIES
from v2.probes.setup.sign_check import LEDGER, run
from v2.probes.setup.writes import TallyWriter, WriteFailed
from v2.tests.probes.fake_books import FakeBooks, sync_client

B = COMPANIES["B"]


def _writer(books):
    return TallyWriter(sync_client(books.transport()), lambda _: None)


def _imports(books):
    return [r for r in books.requests if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in r]


def test_it_creates_a_debit_opening_reads_it_back_raw_and_deletes_the_ledger():
    books = FakeBooks(name=B)
    raw = run(_writer(books), B)
    assert raw == "-1.00"                                    # the fake stores the wire value as sent
    create, delete = _imports(books)
    assert "<PARENT>Sundry Debtors</PARENT>" in create
    assert "<OPENINGBALANCE>-1.00</OPENINGBALANCE>" in create
    assert 'ACTION="Delete"' in delete and LEDGER in delete
    assert LEDGER not in books.state["ledgers"]


def test_an_existing_check_ledger_is_refused_before_anything_is_written():
    """A leftover from an aborted run would be silently skipped by create_party_ledger and its OLD opening read
    back — so refuse, and let the operator delete it."""
    books = FakeBooks(name=B)
    books.edit_state(lambda s: s["ledgers"].__setitem__(LEDGER, {"parent": "Sundry Debtors", "email": "",
                                                                 "alter_id": 1, "guid": "g", "opening": "5.00"}))
    with pytest.raises(WriteFailed, match="already exists"):
        run(_writer(books), B)
    assert _imports(books) == []


def test_the_ledger_is_deleted_even_when_the_read_back_fails():
    books = FakeBooks(name=B)

    def time_out_the_opening_read(body: str) -> None:
        if "S0SignCheckOpening" in body:
            raise httpx.ReadTimeout("no answer")
    books.before_request = time_out_the_opening_read
    with pytest.raises(WriteFailed):
        run(_writer(books), B)
    assert LEDGER not in books.state["ledgers"]
    assert 'ACTION="Delete"' in _imports(books)[-1]
