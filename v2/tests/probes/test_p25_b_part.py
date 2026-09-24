from v2.agent.tally.client import TallyClient
from v2.probes import p25_masters_classification as p25
from v2.probes.capture import Capture
from v2.probes.company_b_view import B_CUSTOM_VOUCHER_TYPE, r9_candidate
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]
NAME, PARENT, OTHER = r9_candidate("educational")


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, io):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p25.PROBE, labels=["B"], client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=io)
    return store.probe_entry(25)["parts"]["B"]


async def test_custom_type_walks_to_sales_and_the_duplicate_is_refused(tmp_path):
    """Ruling S6: a base type found only by the Parent walk is DIFFERENT (spec §7 probe 25; 25 A's live verdict)."""
    io = ScriptedIO(answers=["Duplicate Entry!"])
    part = await _run(tmp_path, _books(), io)
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]
    assert obs["voucher_type"]["resolved_by"] == "Parent walk" and obs["r9"]["verdict"] == "refused"
    assert obs["sub_verdicts"] == {"voucher_type": "DIFFERENT", "duplicate_name": "CONFIRMED"}
    assert "Parent chain" in part["spec_impact"] and "R9" not in part["spec_impact"]
    assert NAME in io.asks[0] and OTHER in io.asks[0]
    assert part["fixtures"] == ["p25_B_voucher_types.xml", "p25_B_ledgers_after_duplicate_attempt.xml"]


async def test_a_custom_type_with_its_base_in_reserved_name_is_confirmed(tmp_path):
    books = _books()
    books.edit_state(lambda s: s.setdefault("voucher_type_reserved", {}).__setitem__(B_CUSTOM_VOUCHER_TYPE, "Sales"))
    part = await _run(tmp_path, books, ScriptedIO(answers=["Duplicate Entry!"]))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["voucher_type"]["resolved_by"] == "ReservedName"
    assert "ReservedName" in part["spec_impact"] and "R9" in part["spec_impact"]


async def test_a_custom_type_without_a_parent_fails(tmp_path):
    part = await _run(tmp_path, _books(voucher_type_parent_exported=False), ScriptedIO(answers=["Duplicate Entry!"]))
    assert part["outcome"] == "FAILED" and "R16" in part["spec_impact"]


async def test_a_saved_duplicate_is_different_and_names_the_cleanup(tmp_path):
    books = _books()
    books.edit_state(lambda s: s.setdefault("duplicate_ledgers", []).append({"name": NAME, "parent": OTHER}))
    part = await _run(tmp_path, books, ScriptedIO(answers=["saved"]))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert "CLEANUP" in part["summary"] and part["observations"]["r9"]["answer_agrees"] is True
    assert "GUID" in part["spec_impact"]


async def test_the_read_back_wins_over_the_operators_answer(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(answers=["saved"]))
    assert part["observations"]["sub_verdicts"]["duplicate_name"] == "CONFIRMED"
    assert part["observations"]["r9"]["verdict"] == "refused" and part["observations"]["r9"]["answer_agrees"] is False


async def test_non_interactive_leaves_r9_unmeasured(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(interactive=False))
    assert part["outcome"] == "DIFFERENT"                       # the Parent walk (S6); R9 not measured
    assert part["observations"]["r9"]["status"].startswith("not attempted")
    assert part["fixtures"] == ["p25_B_voucher_types.xml"]


async def test_auto_mode_never_attempts_the_duplicate(tmp_path):
    io = ScriptedIO(run_mode="auto")
    part = await _run(tmp_path, _books(), io)
    assert "auto mode" in part["observations"]["r9"]["status"] and io.asks == []


async def test_skip_leaves_r9_unmeasured(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(answers=["skip"]))
    assert part["outcome"] == "DIFFERENT" and part["observations"]["r9"]["status"] == "skipped by the operator"


async def test_a_missing_custom_voucher_type_blocks(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["voucherTypes"].remove(B_CUSTOM_VOUCHER_TYPE))
    part = await _run(tmp_path, books, ScriptedIO(answers=["Duplicate Entry!"]))
    assert part["outcome"] == "BLOCKED" and B_CUSTOM_VOUCHER_TYPE in part["summary"]
