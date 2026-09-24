from datetime import date

from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import expect_window
from v2.probes.registry import ALL_ORDER, FIRST_ORDER
from v2.probes.results import ResultsStore
from v2.probes.runner import EDUCATIONAL_SUFFIX, run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, objects_xml, ready_store, vch, vouchers_xml

B = COMPANIES["B"]
JUNE = (date(2023, 6, 1), date(2023, 6, 30))
JUNE_1 = (date(2023, 6, 1), date(2023, 6, 1))
LOADED_AT = "2026-09-24T13:02:33+05:30"


def _store(tmp_path, licence="educational", loaded=True) -> ResultsStore:
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence=licence)
    if loaded:
        store.update_environment(company_b_loaded_at=LOADED_AT)
    return store


async def _run_books(tmp_path, books, **store_kwargs):
    store = _store(tmp_path, **store_kwargs)
    await run_probe(p05.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store, store.probe_entry(5)["parts"]["B"]


def _books(licence="educational") -> FakeBooks:
    books = FakeBooks(name=B)
    seed_company_b(books, licence)
    return books


def _vouchers(window, *, extra=()):
    exp = expect_window("educational", *window)
    return vouchers_xml([vch({"DATE": v.date.strftime("%Y%m%d"), "VOUCHERTYPENAME": v.vch_type,
                              "NARRATION": v.narration}) for v in exp.written.values()] + list(extra))


JULY_STRAY = vch({"DATE": "20230701", "VOUCHERTYPENAME": "Sales", "NARRATION": "[S0-B:301] Sale"})


def _b_tally(month_route, formula_route=None) -> FakeTally:
    fake = FakeTally([B])
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{
        "Name": B, "GUID": "g-b", "AltVchId": "958", "AltMstId": "40", "BooksFrom": "20220401",
        "LastVoucherDate": "20260331", "AlterID": "40"}]))
    fake.route("S0P05MonthFormula", formula_route or (lambda body: vouchers_xml([])))
    fake.route("S0VoucherMonth", month_route)
    return fake


async def _run_fake(tmp_path, fake):
    client, _, capture = make_harness(tmp_path, fake)
    store = _store(tmp_path)
    await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store, store.probe_entry(5)["parts"]["B"]


async def test_typed_svdates_bound_june_2023_and_the_request_is_confirmed(tmp_path):
    store, part = await _run_books(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["month_typed"]["match"] and obs["month_typed"]["returned"] == 20
    assert obs["month_untyped"]["returned"] == 240 and not obs["month_untyped"]["bounded"]
    assert obs["month_untyped"]["date_span"] == ["2025-04-01", "2026-03-31"]
    assert obs["c33_reproduced"] is True
    assert obs["day"]["match"] and obs["day"]["returned"] == 10
    assert obs["report_period_vars"]["identical_bytes"] is False
    assert "C33 reproduced" in part["summary"] and part["summary"].endswith(EDUCATIONAL_SUFFIX)
    assert 'TYPE="Date"' in part["spec_impact"]
    assert part["fixtures"] == ["p05_B_month_svdates.xml", "p05_B_month_svdates_untyped.xml",
                                "p05_B_day_svdates.xml", "p05_B_report_tb_typed.xml", "p05_B_report_tb_untyped.xml"]
    confirmed = store.confirmed("voucher_month")
    assert confirmed["probe"] == 5 and confirmed["form"] == "svdates_typed" and confirmed["day_window_exact"]
    assert '<SVFROMDATE TYPE="Date">__FROM__</SVFROMDATE>' in confirmed["xml_template"]
    assert "<SVCurrentCompany>__COMPANY__</SVCurrentCompany>" in confirmed["xml_template"]


async def test_licensed_books_put_one_voucher_on_the_first(tmp_path):
    _, part = await _run_books(tmp_path, _books("licensed"), licence="licensed")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["day"]["returned"] == 1


async def test_a_licence_that_does_not_match_the_books_shows_in_the_day_window(tmp_path):
    _, part = await _run_books(tmp_path, _books("educational"), licence="licensed")
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["month_typed"]["match"]                  # same 20 tags, all inside June either way
    assert not part["observations"]["day"]["match"] and "half-month" in part["spec_impact"]


async def test_company_b_not_loaded_blocks_before_any_voucher_request(tmp_path):
    books = _books()
    _, part = await _run_books(tmp_path, books, loaded=False)
    assert part["outcome"] == "BLOCKED" and "setup-b" in part["summary"]
    assert not any("<TYPE>Voucher</TYPE>" in r for r in books.requests)


async def test_the_formula_is_confirmed_when_typed_svdates_do_not_bound(tmp_path):
    fake = _b_tally(lambda body: _vouchers(JUNE, extra=[JULY_STRAY]),
                    lambda body: _vouchers(JUNE if '"30-06-2023"' in body else JUNE_1))
    store, part = await _run_fake(tmp_path, fake)
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["month_formula"]["match"] and "$Date formula" in part["spec_impact"]
    confirmed = store.confirmed("voucher_month")
    assert confirmed["form"] == "formula" and "S0P05InWindow" in confirmed["xml_template"]
    assert "__FROM__" in confirmed["xml_template"]
    assert "p05_B_month_formula.xml" in part["fixtures"]


async def test_neither_form_bounding_fails_and_confirms_nothing(tmp_path):
    stray = lambda body: _vouchers(JUNE, extra=[JULY_STRAY])       # noqa: E731
    store, part = await _run_fake(tmp_path, _b_tally(stray, stray))
    assert part["outcome"] == "FAILED"
    assert "filters by date in Python" in part["spec_impact"]
    assert store.confirmed("voucher_month") is None
    assert "p05_B_day_svdates.xml" not in part["fixtures"] and "p05_B_report_tb_typed.xml" in part["fixtures"]


async def test_an_untyped_answer_that_is_also_bounded_is_flagged_not_trusted(tmp_path):
    fake = _b_tally(lambda body: _vouchers(JUNE_1 if "01-06-2023</SVTODATE>" in body else JUNE))
    _, part = await _run_fake(tmp_path, fake)
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["c33_reproduced"] is False
    assert "C33 NOT reproduced" in part["summary"]


def test_ordered_runs_put_probe_5_right_before_probe_21():
    for order in (ALL_ORDER, FIRST_ORDER):
        assert order.index((5, "B")) == order.index((21, "B")) - 1
