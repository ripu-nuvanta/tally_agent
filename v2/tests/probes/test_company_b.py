import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from v2.probes.companies import COMPANIES
from v2.probes.reads import exploded_tb_rows, primary_group_rows
from v2.probes.setup.company_b import (
    CompanyBLoadError, LoadReport, _load_masters, _load_vouchers, _verify, load_company_b,
)
from v2.probes.setup.company_b_data import (
    Dataset, GroupSpec, InventorySpec, LineSpec, UnitSpec, VoucherSpec, generate,
)
from v2.probes.setup.writes import B_READBACK_FROM, B_READBACK_TO, TallyWriter, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, sync_client
from v2.tests.probes.fakes import ScriptedIO

B = COMPANIES["B"]
_SYNC_FIXTURES = Path(__file__).parent.parent / "fixtures" / "sync"
LIVE_A_TB_FY_END = _SYNC_FIXTURES / "p16_A_tb_fy_end.xml"                    # live company A, probe 16, 2026-09-23
LIVE_A_TB_EXPLODED = _SYNC_FIXTURES / "p17_A_tb_exploded_explodealllevels.xml"   # ditto, probe 17

_FLAG_PAUSE_RE = re.compile(r"^\[S0-B:(\d+)\].*?(ISCANCELLED|ISOPTIONAL) did not stick")


def _loader(books, **io_kwargs):
    said: list[str] = []
    writer = TallyWriter(sync_client(books.transport()), said.append)
    return writer, ScriptedIO(**io_kwargs), said


def _empty_b():
    books = FakeBooks(name=B)
    books.edit_state(lambda s: s.update(voucherTypes=["Sales", "Purchase", "Receipt", "Payment", "Sales - GST"]))
    return books


def _operator_who_honours_flag_pauses(books: FakeBooks):
    """F10: the fake never simulates the Tally UI, so a flag pause's re-read fails forever by construction —
    that's an artefact of the fake, not the design. In reality the operator honours the pause and sets the flag
    by hand, and the re-read then sees it (LESSONS/spec §4.3). Mirrors test_p08_ledger_rename.py's
    `on_action`-simulates-the-operator pattern, but for `io.wait` (our pauses carry no `Action` — see the
    module docstring's F2/flag-pause ruling) rather than `io.ask`."""
    def on_wait(instruction: str) -> None:
        match = _FLAG_PAUSE_RE.match(instruction)
        if not match:
            return
        tag, xml_tag = match.group(1), match.group(2)
        field = "cancelled" if xml_tag == "ISCANCELLED" else "optional"

        def fix(s):
            for v in s["vouchers"].values():
                if v["narration"].startswith(f"[S0-B:{tag}]"):
                    v[field] = "Yes"

        books.edit_state(fix)
    return on_wait


def test_a_first_load_lists_before_creating_and_reads_back_every_write():
    books = _empty_b()
    writer, io, _ = _loader(books, on_wait=_operator_who_honours_flag_pauses(books))
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
    books.edit_state(lambda s: s["groups"].__setitem__("National Creditors", {"parent": "Sundry Creditors"}))
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
    books.edit_state(lambda s: s.update(voucherTypes=["Sales", "Purchase", "Receipt", "Payment"]))  # no "Sales - GST"
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
    writer, io, _ = _loader(books, on_wait=_operator_who_honours_flag_pauses(books))
    report = load_company_b(writer, io)
    assert report.problems == []


def test_a_wrong_count_in_an_already_complete_fy_is_reported_as_a_problem_not_swallowed():
    """I2: drift must be flagged only when a chronologically EARLIER FY is short while a LATER one is already
    complete — that's the pattern a date-ordered loader would never produce on its own. Removing the very last
    (most recent) voucher would look identical to a legitimately-interrupted first run and must NOT be flagged
    (see test_a_resumed_run_is_not_flagged_as_drift below) — so this test removes one from the FIRST FY, which
    has three later, fully-loaded FYs proving it should already be complete."""
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)

    def remove_one_from_first_fy(s):
        early_mid = next(mid for mid, v in s["vouchers"].items() if v["date"] < "20230401")
        del s["vouchers"][early_mid]

    books.edit_state(remove_one_from_first_fy)
    report = load_company_b(writer, io)
    assert any("2022-23" in p or "count" in p.lower() for p in report.problems)


def test_a_resumed_run_is_not_flagged_as_drift():
    """I2: the reviewer's reproduction — a partial LATEST FY (nothing later exists yet to prove it "should"
    already be complete) is the state of a legitimately-interrupted first run, not evidence of drift."""
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)

    def remove_one_from_last_fy(s):
        latest_mid = max(s["vouchers"], key=lambda mid: s["vouchers"][mid]["date"])
        del s["vouchers"][latest_mid]

    books.edit_state(remove_one_from_last_fy)
    report = load_company_b(writer, io)
    assert not any("2025-26" in p and "count was" in p for p in report.problems)


def test_educational_mode_only_uses_dates_tally_accepts():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io, licence="educational")
    dates = [v["date"] for v in books.state["vouchers"].values()]
    assert all(int(d[6:8]) in (1, 2, 31) for d in dates)


def test_vouchers_are_imported_in_date_order():                                                              # M3
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    dates = [v["date"] for v in books.state["vouchers"].values()]
    assert dates == sorted(dates)


# --- C1: a failed master create pauses and recovers, never crashes -------------------------------------------------
def test_a_failed_unit_create_pauses_and_recovers_when_the_operator_fixes_it_in_the_ui():
    books = _empty_b()
    books.fail_imports = True
    writer, io, _ = _loader(books)
    tiny = Dataset(groups=(), units=(UnitSpec(name="Box of 10 Nos", first_unit="Box", second_unit="Nos", conversion=10),),
                   items=(), ledgers=(), vouchers=(), licence="licensed")

    def operator_fixes_it(instruction: str) -> None:
        # simulate the operator creating the unit by hand in the Tally UI (bypassing the fake's fail_imports,
        # which only gates the XML import path)
        books.edit_state(lambda s: s["units"].__setitem__("Box of 10 Nos", {"base": "Nos", "conversion": "10"}))

    io2 = ScriptedIO(on_wait=operator_fixes_it)
    report = LoadReport()
    _load_masters(writer, io2, B, tiny, report)          # must not raise
    assert any("Box of 10 Nos" in p for p in report.pauses)


def test_a_failed_master_create_raises_if_the_operator_never_fixes_it():
    books = _empty_b()
    books.fail_imports = True
    writer, io, _ = _loader(books)
    tiny = Dataset(groups=(GroupSpec(name="National Creditors", parent="Sundry Creditors"),),
                   units=(), items=(), ledgers=(), vouchers=(), licence="licensed")
    report = LoadReport()
    with pytest.raises(CompanyBLoadError, match="National Creditors"):
        _load_masters(writer, io, B, tiny, report)
    assert any("National Creditors" in p for p in report.pauses)


def test_a_failed_voucher_create_pauses_and_recovers_when_the_operator_fixes_it_in_the_ui():
    """C1's crash guard was extended to voucher creates (same failure class as master creates) but had no test
    of its own — this is that test, structured exactly like the master-create one above."""
    books = _empty_b()
    books.fail_imports = True
    writer, io, _ = _loader(books)
    tiny_voucher = VoucherSpec(
        tag=999, kind="payment", vch_type="Payment", date=date(2025, 6, 1), party="Office Rent",
        narration="[S0-B:999] Payment for Office Rent",
        lines=(LineSpec(ledger="Office Rent", amount=Decimal("100.00"), deemed_positive=True),
               LineSpec(ledger="HDFC Bank Current A/c", amount=Decimal("-100.00"), deemed_positive=False)),
        inventory=(), bills=())
    tiny = Dataset(groups=(), units=(), items=(), ledgers=(), vouchers=(tiny_voucher,), licence="licensed")

    def operator_creates_it(instruction: str) -> None:
        # simulate the operator creating the voucher by hand in the Tally UI (bypassing the fake's
        # fail_imports, which only gates the XML import path)
        books.edit_state(lambda s: s["vouchers"].__setitem__(
            "9001", {"narration": tiny_voucher.narration, "date": "20250601", "post_dated": "No",
                     "cancelled": "No", "optional": "No", "lines": []}))

    io2 = ScriptedIO(on_wait=operator_creates_it)
    report = LoadReport()
    _load_vouchers(writer, io2, B, tiny, report)          # must not raise
    assert any("[S0-B:999]" in p for p in report.pauses)
    assert report.created["vouchers"] == 0
    assert report.skipped["vouchers"] == 1


def test_a_failed_voucher_create_raises_if_the_operator_never_fixes_it():
    books = _empty_b()
    books.fail_imports = True
    writer, io, _ = _loader(books)
    tiny_voucher = VoucherSpec(
        tag=999, kind="payment", vch_type="Payment", date=date(2025, 6, 1), party="Office Rent",
        narration="[S0-B:999] Payment for Office Rent",
        lines=(LineSpec(ledger="Office Rent", amount=Decimal("100.00"), deemed_positive=True),
               LineSpec(ledger="HDFC Bank Current A/c", amount=Decimal("-100.00"), deemed_positive=False)),
        inventory=(), bills=())
    tiny = Dataset(groups=(), units=(), items=(), ledgers=(), vouchers=(tiny_voucher,), licence="licensed")
    report = LoadReport()
    with pytest.raises(CompanyBLoadError, match=r"S0-B:999"):
        _load_vouchers(writer, io, B, tiny, report)
    assert any("[S0-B:999]" in p for p in report.pauses)


# --- C2: `_verify` has real, direct coverage -------------------------------------------------------------------
def test_verify_reports_a_voucher_count_mismatch_directly():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    ds = generate()
    books.edit_state(lambda s: s["vouchers"].popitem())      # doctor the books; no second load, so no healing
    report = LoadReport()
    _verify(writer, B, ds, report)
    assert any("count" in p.lower() for p in report.problems)


def test_verify_reports_a_whole_missing_fy():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    ds = generate()

    def wipe_2022_23(s):
        s["vouchers"] = {mid: v for mid, v in s["vouchers"].items() if not ("20220401" <= v["date"] <= "20230331")}

    books.edit_state(wipe_2022_23)
    report = LoadReport()
    _verify(writer, B, ds, report)
    assert any("2022-23" in p for p in report.problems)


def test_verify_passes_when_nothing_was_doctored():
    """The negative case C2 asked for: `_verify` doesn't touch flags at all (that's `_settle_flags`'s job), so
    with F9's opening-balance fix this is a genuine `problems == []` — not a default, not a whitelist. The other
    two `_verify`-direct tests above prove it can find something real; this proves it doesn't cry wolf."""
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    ds = generate()
    report = LoadReport()
    _verify(writer, B, ds, report)
    assert report.problems == []


def test_verify_reports_a_duplicated_voucher():
    """I4: `_read_vouchers` used to key rows by tag, last-wins, and `_verify` counted the dict's values — so 960
    vouchers plus a duplicate read as exactly 960 and the run came back clean. Ruling C17's whole rationale is
    that a duplicate is worse than a gap, so the verifier must be able to see one: the raw row count now drives
    the per-FY comparison, and any tag seen more than once gets its own `problems` line."""
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)

    def duplicate_one_voucher(s):
        mid, v = next((mid, v) for mid, v in s["vouchers"].items() if v["narration"].startswith("[S0-B:5]"))
        s["vouchers"]["90001"] = dict(v)          # the same tag, a second Master ID — what a re-run would land

    books.edit_state(duplicate_one_voucher)
    report = LoadReport()
    _verify(writer, B, generate(), report)
    assert any("[S0-B:5]" in p and "duplicate" in p.lower() for p in report.problems)
    assert any("count mismatch" in p for p in report.problems)     # and the FY count sees the extra copy too


# --- C3: group-level balance verification --------------------------------------------------------------------
def test_verify_reports_a_group_balance_mismatch():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    ds = generate()

    def corrupt_one_line(s):
        _mid, v = next(iter(s["vouchers"].items()))
        line = v["lines"][0]
        line["amount"] = str(Decimal(line["amount"]) + Decimal("500.00"))

    books.edit_state(corrupt_one_line)
    report = LoadReport()
    _verify(writer, B, ds, report)
    assert any("balance" in p.lower() for p in report.problems)


def _second_level(rows: list[dict]) -> dict[str, Decimal]:
    """First row per account name, the same way `_verify_balances` picks its comparison rows."""
    out: dict[str, Decimal] = {}
    for row in rows:
        if row["account_name"] not in out and row["closing_balance"] is not None:
            out[row["account_name"]] = row["closing_balance"]
    return out


def test_the_fakes_trial_balance_matches_the_live_fixtures_sign_pattern():
    """F15: `_verify_balances` had been an identity check — the fake replays the exact line amounts the
    expectation is built from, so it could never disagree with itself. That proves nothing about whether either
    side matches REALITY. This test pins polarity against a real Tally export instead: if the fake's TB — built
    from a completely independent code path (FakeBooks' own group-nature inference, not `company_b_data.py`'s
    dataset) — landed on the OPPOSITE polarity, this is what would catch a "corrected" F12 that over-corrected
    into the mirror image. It does not prove the live run will show this (only the live run can).

    I3 (final review) — RE-ANCHORED, and two assertions deliberately changed:

    * The anchor was `fixtures/tally_samples/trial_balance_live.xml`, whose own SOURCE.md says verbatim "parser
      tests only, never seed-parity anchors" (it is the NUVANTA company's data, not the seed company). It now
      anchors to this project's OWN live company-A captures, `p16_A_tb_fy_end.xml` and
      `p17_A_tb_exploded_explodealllevels.xml` (probe 16/17, live 2026-09-23), and asserts they agree.
    * `Current Assets < 0` is GONE, on both halves. That assertion came from the forbidden fixture and is
      contradicted by company A's own live capture, which shows Current Assets **+2,605,093.00** — because A's
      `Bank Accounts` (+1,696,830) and `Cash-in-Hand` (+23,000) carry the wrong sign for debit-natured groups,
      the known seed defect the tracker records. Those two buckets are therefore deliberately NOT asserted
      here either. In their place this pins the second-level buckets `_verify_balances` actually compares and
      whose live signs are trustworthy: Sundry Debtors (debit, negative), Sundry Creditors (credit, positive),
      Duties & Taxes (net input GST, debit, negative).
    """
    live_rows = exploded_tb_rows(LIVE_A_TB_FY_END.read_text(encoding="utf-8"))
    exploded_rows = exploded_tb_rows(LIVE_A_TB_EXPLODED.read_text(encoding="utf-8"))
    live, live_second = primary_group_rows(live_rows), _second_level(live_rows)
    exploded_second = _second_level(exploded_rows)                          # the two live exports agree on
    assert {k: v for k, v in exploded_second.items() if k in live_second} == live_second   # every shared bucket
    assert live["Capital Account"]["closing_balance"] > 0
    assert live["Sales Accounts"]["closing_balance"] > 0
    assert live["Purchase Accounts"]["closing_balance"] < 0
    assert live["Indirect Expenses"]["closing_balance"] < 0
    assert live_second["Sundry Debtors"] < 0
    assert live_second["Sundry Creditors"] > 0
    assert live_second["Duties & Taxes"] < 0

    books = _empty_b()
    writer, io, _ = _loader(books, on_wait=_operator_who_honours_flag_pauses(books))
    load_company_b(writer, io)
    fake_rows = exploded_tb_rows(writer.b_trial_balance(B, B_READBACK_FROM, B_READBACK_TO))
    fake, fake_second = primary_group_rows(fake_rows), _second_level(fake_rows)
    assert fake["Capital Account"]["closing_balance"] > 0
    assert fake["Sales Accounts"]["closing_balance"] > 0
    assert fake["Purchase Accounts"]["closing_balance"] < 0
    assert fake["Indirect Expenses"]["closing_balance"] < 0
    assert fake_second["Sundry Debtors"] < 0
    assert fake_second["Sundry Creditors"] > 0
    assert fake_second["Duties & Taxes"] < 0


# --- I1: the flag pause re-reads and reports if it still didn't take -----------------------------------------------
def test_a_flag_that_never_sticks_is_reported_as_a_problem_after_the_reread():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    # ISCANCELLED is never written at all (create_b_voucher's own docstring) and nothing in this fake simulates
    # an operator fixing it, so the re-read after the pause must still find it wrong.
    assert any("[S0-B:201]" in p and "ISCANCELLED" in p for p in report.problems)


# --- I3: the four flag-tagged vouchers are never auto-recreated on a resumed run --------------------------------
def test_a_missing_flagged_voucher_on_a_resumed_run_is_not_recreated():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)

    def remove_tag_201(s):
        mid = next(mid for mid, v in s["vouchers"].items() if v["narration"].startswith("[S0-B:201]"))
        del s["vouchers"][mid]

    books.edit_state(remove_tag_201)
    report = load_company_b(writer, io)
    assert report.created["vouchers"] == 0
    assert report.skipped["vouchers"] == 959
    assert any("[S0-B:201]" in p for p in report.problems)
    assert any("[S0-B:201]" in p for p in report.pauses)


# --- I4: an existing master under the wrong parent/base unit is flagged --------------------------------------------
def test_an_existing_ledger_under_the_wrong_parent_is_flagged():
    books = _empty_b()
    books.edit_state(lambda s: s["ledgers"].__setitem__(
        "Delhi Metal Traders", {"parent": "Sundry Creditors", "email": "", "alter_id": 999, "guid": "x"}))
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert any("Delhi Metal Traders" in p and "Sundry Creditors" in p for p in report.problems)


def test_an_existing_item_under_the_wrong_base_unit_is_flagged():
    books = _empty_b()
    books.edit_state(lambda s: s["items"].__setitem__("USB Cable Type-C", {"parent": "", "base_units": "Box of 10 Nos"}))
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert any("USB Cable Type-C" in p for p in report.problems)


# --- I5: the opening-bill pause is read-verified, not unconditional ------------------------------------------------
def test_the_opening_bill_pauses_when_absent():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert any("Op/2022-001" in p for p in report.pauses)


def test_the_opening_bill_pause_is_skipped_when_the_bill_is_already_there():
    books = _empty_b()
    books.edit_state(lambda s: s.update(bills_receivable=[("Op/2022-001", "Pune Digital Solutions", "62500.00")]))
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert not any("Op/2022-001" in p for p in report.pauses)


# --- M2: the line-ordering contract is a real stop, not a bare `assert` --------------------------------------------
def test_an_inventory_voucher_whose_party_is_not_the_first_line_stops_the_load():
    """M2: `create_b_voucher` can only check `len(lines) >= 2` (ledger names carry no semantic tag), so the
    party-first contract lives here. It used to be a bare `assert`: gone under `python -O`, and an
    AssertionError is not caught by `_load_vouchers`' `except WriteFailed`, so it crashed the load mid-run
    rather than stopping it readably."""
    books = _empty_b()
    writer, io, _ = _loader(books)
    misordered = VoucherSpec(
        tag=998, kind="sales", vch_type="Sales", date=date(2025, 6, 1), party="Pune Digital Solutions",
        narration="[S0-B:998] Sale to Pune Digital Solutions",
        lines=(LineSpec(ledger="Domestic Sales", amount=Decimal("1000.00"), deemed_positive=False),
               LineSpec(ledger="Pune Digital Solutions", amount=Decimal("-1000.00"), deemed_positive=True)),
        inventory=(InventorySpec(item="USB Cable Type-C", qty=Decimal("1"), rate=Decimal("1000.00"),
                                 amount=Decimal("1000.00")),),
        bills=())
    tiny = Dataset(groups=(), units=(), items=generate().items, ledgers=(), vouchers=(misordered,),
                   licence="licensed")
    report = LoadReport()
    with pytest.raises(CompanyBLoadError, match="must list the party"):
        _load_vouchers(writer, io, B, tiny, report)
    assert [r for r in books.requests if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in r] == []
