from v2.agent.tally.client import TallyClient
from v2.probes import p11_openings as p11
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p11.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store.probe_entry(11)["parts"]["B"]


async def test_openings_straight_from_the_masters_are_confirmed(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["ledgers"]["mismatched"] == {} and obs["opening_bill"]["candidate"]["magnitude_match"] is True
    assert obs["stock"]["A4 Paper Ream"]["qty_ok"] and obs["stock"]["USB Cable Type-C"]["value_ok"]
    assert part["fixtures"] == ["p11_B_ledger_openings.xml", "p11_B_opening_bills.xml", "p11_B_stock_openings.xml"]


async def test_opening_bill_only_in_the_report_is_different(tmp_path):
    part = await _run(tmp_path, _books(ledger_opening_bills_exported=False))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["opening_bill"]["report"]["found"] is True
    assert "p11_B_opening_bills_report.xml" in part["fixtures"]
    assert "Bills Receivable" in part["spec_impact"]


async def test_fy_scoped_ledger_openings_are_different_and_point_at_probe_16(tmp_path):
    part = await _run(tmp_path, _books(ledger_opening_scope="fy"))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]["ledgers"]
    assert obs["mismatched"] and set(obs["as_current_fy"]) == set(obs["mismatched"])
    assert "probe 16 B" in part["spec_impact"]


async def test_stock_value_exported_positive_is_different(tmp_path):
    books = _books()
    books.edit_state(lambda s: [i.__setitem__("opening_value", i["opening_value"].lstrip("-"))
                                for i in s["items"].values()])
    part = await _run(tmp_path, books)
    assert part["outcome"] == "DIFFERENT" and part["observations"]["stock"]["USB Cable Type-C"]["value_sign_flipped"]


async def test_wrong_stock_quantity_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["items"]["USB Cable Type-C"].__setitem__("opening_qty", "100 Nos"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "USB Cable Type-C" in part["summary"]


async def test_a_missing_ledger_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"].pop("Satara Packaging Co"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "Satara Packaging Co" in part["summary"]
