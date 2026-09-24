from v2.agent.tally.client import TallyClient
from v2.probes import p14_special_char_company as p14
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
    await run_probe(p14.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store.probe_entry(14)["parts"]["B"]


def test_unescaped_puts_the_raw_name_back_and_nothing_else():
    xml = p14.escaped_request(B)
    raw = p14.unescaped(xml, B)
    assert "<SVCurrentCompany>Sharma & Sons' Probe Traders</SVCurrentCompany>" in raw
    assert raw.replace("Sharma & Sons' Probe Traders", "Sharma &amp; Sons&apos; Probe Traders") == xml


async def test_escaped_works_unescaped_fails_confirmed(tmp_path):
    part = await _run(tmp_path, _books(honour_company_var=True))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["escaped"]["ok"] and obs["escaped"]["has_hindi"] and not obs["unescaped"]["ok"]
    assert obs["unescaped"]["error"] and obs["unknown_company"]["ok"] is False
    assert part["fixtures"] == ["p14_B_escaped_request.xml", "p14_B_unknown_company_request.xml",
                                "p14_B_unescaped_request.xml"]


async def test_a_tally_that_ignores_the_company_variable_is_still_confirmed_with_a_gate_note(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED" and part["observations"]["unknown_company"]["ok"] is True
    assert "probe 2" in part["spec_impact"]


async def test_a_tally_that_tolerates_the_raw_ampersand_is_different(tmp_path):
    part = await _run(tmp_path, _books(honour_company_var=True, tolerate_raw_ampersand=True))
    assert part["outcome"] == "DIFFERENT" and part["observations"]["unescaped"]["ok"] is True


async def test_a_wedge_after_the_unescaped_request_blocks_with_the_popup_hint(tmp_path):
    books = _books(honour_company_var=True)

    def wedge_on_raw_name(body: str) -> None:
        if "<SVCurrentCompany>Sharma & Sons'" in body:
            books.popup = True
    books.before_request = wedge_on_raw_name
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "popup" in part["summary"].lower()
    assert part["observations"]["unescaped"]["kind"] == "timeout"


def test_probe_14_runs_last_in_company_b():
    """Ruling Q6 (spec §6 batch 5, Changed 2026-09-24): 14 deliberately sends malformed XML that may upset Tally, so
    every other company-B probe — 15 included — runs before it."""
    from v2.probes.registry import ALL_ORDER
    b_steps = [step for step, label in ALL_ORDER if label == "B"]
    assert b_steps[-1] == 14 and b_steps.index(15) < b_steps.index(14)
