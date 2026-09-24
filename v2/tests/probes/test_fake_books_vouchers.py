from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER
from v2.probes.companies import COMPANIES
from v2.probes.p01_company_counters import COUNTERS_REQUEST
from v2.probes.reads import (FROM_PLACEHOLDER, TO_PLACEHOLDER, VOUCHER_MONTH_FIELDS, fill_month_request,
                             parse_vouchers, untyped_period_vars, voucher_request)
from v2.agent.tally.xml_utils import read_objects
from v2.tests.probes.fake_books import FakeBooks, seed_company_b, sync_client

B = COMPANIES["B"]
TEMPLATE = voucher_request("S0VoucherMonth", VOUCHER_MONTH_FIELDS, COMPANY_PLACEHOLDER,
                           from_date=FROM_PLACEHOLDER, to_date=TO_PLACEHOLDER)


def _post(books: FakeBooks, xml: str) -> str:
    with sync_client(books.transport()) as client:
        return client.post("/", content=xml.encode("utf-8")).text


def _seeded(licence="educational") -> FakeBooks:
    books = FakeBooks(name=B)
    seed_company_b(books, licence)
    return books


def test_seeded_company_b_holds_every_written_voucher_with_its_flags():
    state = _seeded().state
    by_tag = {v["narration"].split("]")[0] + "]": v for v in state["vouchers"].values()}
    assert len(state["vouchers"]) == 958                              # 960 minus the skipped USD sales (C36)
    assert "[S0-B:101]" not in by_tag and "[S0-B:102]" not in by_tag
    assert by_tag["[S0-B:201]"]["cancelled"] == "Yes" and by_tag["[S0-B:302]"]["optional"] == "Yes"
    assert by_tag["[S0-B:1]"]["cancelled"] == by_tag["[S0-B:1]"]["optional"] == "No"
    assert state["books_from"] == "20220401"


def test_a_typed_month_returns_exactly_that_month_in_full():
    vouchers = parse_vouchers(_post(_seeded(), fill_month_request(TEMPLATE, B, "01-06-2023", "30-06-2023")))
    assert len(vouchers) == 20
    assert {v["header"]["DATE"][:6] for v in vouchers} == {"202306"}
    sale = next(v for v in vouchers if v["header"]["NARRATION"].startswith("[S0-B:281]"))
    assert sale["header"]["VOUCHERTYPENAME"] in ("Sales", "Sales - GST") and sale["header"]["GUID"]
    assert sale["ledger_lines"][0]["bills"][0]["BILLTYPE"] == "New Ref"
    assert len(sale["inventory"]) == 1


def test_an_untyped_window_silently_answers_for_the_current_period():
    xml = untyped_period_vars(fill_month_request(TEMPLATE, B, "01-06-2023", "30-06-2023"))
    dates = sorted(v["header"]["DATE"] for v in parse_vouchers(_post(_seeded(), xml)))
    assert len(dates) == 240 and (dates[0], dates[-1]) == ("20250401", "20260331")


def test_counters_report_books_from_from_state():
    def books_from(books):
        return read_objects(_post(books, COUNTERS_REQUEST), "COMPANY", ["BooksFrom"])[0]["BooksFrom"]
    assert books_from(FakeBooks()) == "20250401"
    assert books_from(_seeded()) == "20220401"
