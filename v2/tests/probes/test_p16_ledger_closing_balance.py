from decimal import Decimal

import httpx

from v2.probes import p16_ledger_closing_balance as p16
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import (COMPANY_A, ScriptedIO, a_tally, line, make_harness, objects_xml, ready_store,
                                   stock_summary_xml, tb_xml, vch, vouchers_xml)

APEX, HP = "Apex Technologies Pvt Ltd", "HP India Sales Pvt Ltd"
GROUPS = [
    {"Name": "Current Assets", "Parent": "Primary"}, {"Name": "Sundry Debtors", "Parent": "Current Assets"},
    {"Name": "North Zone Debtors", "Parent": "Sundry Debtors"}, {"Name": "Cash-in-Hand", "Parent": "Current Assets"},
    {"Name": "Stock-in-Hand", "Parent": "Current Assets"}, {"Name": "Current Liabilities", "Parent": "Primary"},
    {"Name": "Sundry Creditors", "Parent": "Current Liabilities"},
    {"Name": "National Creditors", "Parent": "Sundry Creditors"}, {"Name": "Capital Account", "Parent": "Primary"},
    {"Name": "Sales Accounts", "Parent": "Primary"}, {"Name": "Purchase Accounts", "Parent": "Primary"},
    {"Name": "Indirect Expenses", "Parent": "Primary"},
]
VOUCHERS = vouchers_xml([
    vch({"DATE": "20251015", "VOUCHERTYPENAME": "Sales"}, lines=[line(APEX, "-970537.00"), line("Sales", "970537.00")]),
    vch({"DATE": "20250910", "VOUCHERTYPENAME": "Purchase"},
        lines=[line(HP, "1834142.00"), line("Purchases", "-1834142.00")]),
    vch({"DATE": "20251105", "VOUCHERTYPENAME": "Payment"}, lines=[line("Electricity", "-100.00"), line("Cash", "100.00")]),
])
TB = tb_xml([("Capital Account", "", "1000.00"), ("Current Liabilities", "", "1834142.00"),
             ("Current Assets", "-971437.00", ""), ("Sales Accounts", "", "970537.00"),
             ("Purchase Accounts", "-1834142.00", ""), ("Indirect Expenses", "-100.00", "")])
TB_WITH_STOCK = tb_xml([("Capital Account", "", "1000.00"), ("Current Liabilities", "", "1834142.00"),
                        ("Current Assets", "-976437.00", ""), ("Sales Accounts", "", "970537.00"),
                        ("Purchase Accounts", "-1834142.00", ""), ("Indirect Expenses", "-100.00", "")])


def _ledger(name, parent, opening="", closing=""):
    return {"Name": name, "Parent": parent, "OpeningBalance": opening, "ClosingBalance": closing}


ASOF = [_ledger(APEX, "North Zone Debtors", closing="-970537.00"), _ledger(HP, "National Creditors", closing="1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", "-1000.00"), _ledger("Capital Account", "Capital Account", "1000.00", "1000.00")]
FROM = [_ledger(APEX, "North Zone Debtors", "", "-970537.00"), _ledger(HP, "National Creditors", "1834142.00", "1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", "-1000.00"), _ledger("Capital Account", "Capital Account", "1000.00", "1000.00")]


def _fy_ledgers(state):
    cash = (Decimal("-900.00") + (1 if state["future"] and state["future_counts"] else 0)
            + (1 if state["post_dated"] and state["pd_counts"] else 0))
    return [
        _ledger(APEX, "North Zone Debtors", closing="-970537.00"),
        _ledger(HP, "National Creditors", closing="1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", state.get("cash_override") or f"{cash:.2f}"),
        _ledger("Capital Account", "Capital Account", "1000.00", "1000.00"),
        _ledger("Sales", "Sales Accounts"), _ledger("Purchases", "Purchase Accounts"),
        _ledger("Electricity", "Indirect Expenses", closing=state.get("electricity", "")),
        _ledger("Profit & Loss A/c", "Primary"),
    ]


def _fake(**overrides):
    state = {"future": False, "future_counts": True, "post_dated": False, "pd_counts": False, "as_on": True, "tb": TB,
             "stock": "0.00", "pd_export": "Yes", "last_voucher_date": "20260301", **overrides}
    fake, _ = a_tally()
    fake.routes = [(m, h) for m, h in fake.routes if m != "S0CompanyCounters"]
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{
        "Name": COMPANY_A, "GUID": "g-1", "AltVchId": "50", "AltMstId": "266", "BooksFrom": "20250401",
        "LastVoucherDate": state["last_voucher_date"], "AlterID": "266"}]))

    def ledgers(body):
        if state["as_on"] and "<SVTODATE>31-10-2025</SVTODATE>" in body:
            return objects_xml("LEDGER", FROM if "<SVFROMDATE>01-10-2025</SVFROMDATE>" in body else ASOF)
        return objects_xml("LEDGER", _fy_ledgers(state))

    def throwaways(body):
        rows = []
        if state["future"]:
            rows.append(vch({"DATE": "20260331", "NARRATION": p16.FUTURE_NARRATION, "ISPOSTDATED": "No", "MASTERID": "51"}))
        if state["post_dated"]:
            rows.append(vch({"DATE": "20260331", "NARRATION": p16.POST_DATED_NARRATION, "ISPOSTDATED": state["pd_export"],
                             "MASTERID": "52"}))
        return vouchers_xml(rows)

    fake.route("S0P16Ledgers", ledgers)
    fake.route("S0P16Groups", lambda body: objects_xml("GROUP", GROUPS))
    fake.route("S0P16Vouchers", lambda body: VOUCHERS)
    fake.route("S0P16Throwaway", throwaways)
    fake.route("<ID>Trial Balance</ID>", lambda body: state["tb"])
    fake.route("<ID>Stock Summary</ID>", lambda body: stock_summary_xml([("Electronics", "60 Nos", "", state["stock"])]))

    def on_action(action):
        key = "future" if action.params["ref"] == p16.FUTURE_REF else "post_dated"
        state[key] = action.kind == "create_voucher"

    return fake, on_action


def _io(on_action, answers=None):
    return ScriptedIO(on_action=on_action, answers=answers,
                      answers_by_kind=None if answers else {"ui_closing_balance": ""})


async def _run(tmp_path, fake, io, p01_last_voucher_date=None):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, p01_last_voucher_date=p01_last_voucher_date)
    outcome = await run_probe(p16.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return outcome, store, store.probe_entry(16)["parts"]["A"]


async def test_confirmed_path_records_the_rung1_rule(tmp_path):
    fake, on_action = _fake()
    io = _io(on_action)
    outcome, store, part = await _run(tmp_path, fake, io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert outcome is Outcome.PARTIAL and store.probe_entry(16)["remaining"] == ["B"]
    obs = part["observations"]
    assert obs["as_on"]["closing_follows_svtodate"] is True and obs["as_on"]["opening_follows_svfromdate"] is True
    assert obs["future_voucher"]["included_in_closing"] is True
    assert obs["post_dated_voucher"]["included_in_closing"] is False
    assert obs["post_dated_voucher"]["is_post_dated_exported"] == "Yes"
    assert "the period end" in part["spec_impact"] and "post-dated vouchers are excluded" in part["spec_impact"]
    assert "UI balances not read" in part["summary"]
    assert [a.kind for a in io.actions] == ["create_voucher", "delete_voucher", "create_voucher", "delete_voucher"]
    assert io.actions[2].params["post_dated"] is True
    assert part["fixtures"] == [
        "p16_A_ledgers.xml", "p16_A_groups.xml", "p16_A_vouchers_fy.xml", "p16_A_tb_fy_end.xml",
        "p16_A_stock_summary_fy_end.xml", "p16_A_ledgers_asof_2025-10-31.xml", "p16_A_ledgers_from_2025-10-01.xml",
        "p16_A_future_voucher.xml", "p16_A_ledgers_with_future_voucher.xml", "p16_A_post_dated_voucher.xml",
        "p16_A_ledgers_with_post_dated.xml",
    ]


async def test_closing_not_matching_lines_fails(tmp_path):
    fake, on_action = _fake(cash_override="-800.00")
    outcome, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "FAILED"
    assert "Cash" in part["summary"] and "rung 1 collapses" in part["spec_impact"]
    assert "As-on works" in part["spec_impact"]   # M1: the FAILED spec_impact carries the as-on sentence too


async def test_ui_balance_mismatch_fails(tmp_path):
    fake, on_action = _fake()
    _, _, part = await _run(tmp_path, fake, _io(on_action, answers=["1.00 Dr", "", ""]))
    assert part["outcome"] == "FAILED"
    assert "Tally UI shows another balance for Apex Technologies Pvt Ltd" in part["summary"]


async def test_tb_row_explained_by_closing_stock_is_different(tmp_path):
    fake, on_action = _fake(tb=TB_WITH_STOCK, stock="5000.00")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["tb_vs_rollup"]["Current Assets"]["explained_by_stock"] is True
    assert "Stock Summary" in part["spec_impact"]


async def test_nonzero_nominal_ledger_is_different(tmp_path):
    fake, on_action = _fake(electricity="-100.00")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    assert "nominal ledger(s)" in part["summary"]
    assert part["observations"]["nominal"]["nonzero"] == {"Electricity": Decimal("-100.00")}   # in memory: Decimal


async def test_as_on_ignored_is_recorded_not_failed(tmp_path):
    fake, on_action = _fake(as_on=False)
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["as_on"]["closing_follows_svtodate"] is False
    assert "depend on probe 17" in part["spec_impact"]


async def test_throwaway_voucher_has_a_cleanup_note_until_deleted(tmp_path):
    fake, on_action = _fake()
    fake.routes = [(m, h) for m, h in fake.routes if m != "S0P16Throwaway"]
    fake.route("S0P16Throwaway", lambda body: httpx.ReadTimeout)
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "BLOCKED"
    assert part["observations"]["cleanup_needed"] == [
        f"Delete the voucher with narration {p16.FUTURE_NARRATION!r} if it still exists"]


# --- M4: the post-dated rule stays open if IsPostDated didn't stick -------------------------------------------------


async def test_post_dated_flag_not_sticking_leaves_the_rule_open(tmp_path):
    fake, on_action = _fake(pd_export="No")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["post_dated_voucher"]["is_post_dated_exported"] == "No"
    assert "the flag didn't stick" in part["spec_impact"] and "post-dated rule is still open" in part["spec_impact"]
    assert "post-dated vouchers are" not in part["spec_impact"]


# --- M6: the as-of (F2 vs period end) verdict rests on the pre-run books reach, not on a polluted reading ----------


async def test_probe1_baseline_settles_the_asof_rule_in_the_planned_order(tmp_path):
    """In ALL_ORDER/FIRST_ORDER probe 1 runs immediately before probe 16 and leaves LastVoucherDate at 20260331
    (it doesn't roll back on delete), so probe 16's own reading is useless. Probe 1's recorded pre-throwaway
    baseline still settles it."""
    fake, on_action = _fake(last_voucher_date="20260331")          # probe 1's leftover, as live
    _, _, part = await _run(tmp_path, fake, _io(on_action), p01_last_voucher_date="20260301")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["last_voucher_date"] == "20260331"
    assert "ClosingBalance is as of the period end (31-03-2026), not Tally's current date" in part["spec_impact"]
    assert "inconclusive" not in part["spec_impact"]
    basis = part["observations"]["as_of_basis"]
    assert basis["verdict"] == "period_end"
    assert basis["books_reach_before_run"] == "20260301" and basis["available"] is True
    assert "probe 1's baseline" in basis["source"]


async def test_books_already_reaching_the_period_end_before_the_run_is_inconclusive_with_a_rerun_recipe(tmp_path):
    fake, on_action = _fake(last_voucher_date="20260331")
    _, _, part = await _run(tmp_path, fake, _io(on_action), p01_last_voucher_date="20260331")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["as_of_basis"]["verdict"] == "inconclusive"
    assert "inconclusive: the throwaway voucher dated 31-Mar-2026 is in ClosingBalance" in part["spec_impact"]
    assert "the books already reached 20260331 before this run" in part["spec_impact"]
    assert "reset-a" in part["spec_impact"] and "run 16 --company A --rerun" in part["spec_impact"]
    assert "not Tally's current date" not in part["spec_impact"]


async def test_no_last_voucher_date_at_all_is_recorded_as_not_available_not_as_safe(tmp_path):
    """p01 drops fields the Company collection exports empty, so LastVoucherDate can be missing: that must read as
    'not available' (no verdict), never as an empty string quietly passing the < cutoff test."""
    fake, on_action = _fake(last_voucher_date="")
    _, _, part = await _run(tmp_path, fake, _io(on_action), p01_last_voucher_date="")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    basis = part["observations"]["as_of_basis"]
    assert basis["verdict"] == "inconclusive" and basis["available"] is False
    assert basis["source"] == "not available: probe 1 recorded no LastVoucherDate for this company"
    assert "the pre-run LastVoucherDate is not available" in part["spec_impact"]
    assert "reset-a" in part["spec_impact"]


async def test_a_future_voucher_left_out_of_closing_settles_it_whatever_the_books_reach(tmp_path):
    """A balance as of the period end would contain a voucher dated on the period end, so "not included" names the
    current date soundly — no books-reach guard needed."""
    fake, on_action = _fake(last_voucher_date="20260331", future_counts=False)
    _, _, part = await _run(tmp_path, fake, _io(on_action), p01_last_voucher_date="20260331")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["future_voucher"]["included_in_closing"] is False
    assert part["observations"]["as_of_basis"]["verdict"] == "current_date"
    assert "ClosingBalance is as of Tally's current date (F2), not the period end" in part["spec_impact"]
    assert "inconclusive" not in part["spec_impact"]


async def test_without_a_recorded_baseline_probe16_falls_back_to_its_own_reading(tmp_path):
    fake, on_action = _fake(last_voucher_date="20260401")
    _, _, part = await _run(tmp_path, fake, _io(on_action))          # probe 1 recorded no baseline
    basis = part["observations"]["as_of_basis"]
    assert basis["verdict"] == "inconclusive" and basis["books_reach_before_run"] == "20260401"
    assert "probe 16's own reading" in basis["source"]
    assert "reset-a" in part["spec_impact"]


# --- M7: an unbalanced voucher makes the lines check inconclusive, not a FAILED ---------------------------------------


async def test_unbalanced_voucher_makes_the_lines_check_inconclusive_not_failed(tmp_path):
    unbalanced_vouchers = vouchers_xml([
        vch({"DATE": "20251015", "VOUCHERTYPENAME": "Sales"}, lines=[line(APEX, "-970537.00"), line("Sales", "970537.00")]),
        vch({"DATE": "20250910", "VOUCHERTYPENAME": "Purchase"},
            lines=[line(HP, "1834142.00"), line("Purchases", "-1834142.00")]),
        vch({"DATE": "20251105", "VOUCHERTYPENAME": "Payment"},
            lines=[line("Electricity", "-100.00"), line("Cash", "50.00")]),   # -100 + 50 = -50: doesn't balance
    ])
    fake, on_action = _fake()
    fake.routes = [(m, h) for m, h in fake.routes if m != "S0P16Vouchers"]
    fake.route("S0P16Vouchers", lambda body: unbalanced_vouchers)
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["unbalanced_vouchers"]
    assert "posting rule unverified (probe 6 decides); lines check inconclusive" in part["spec_impact"]
    assert "Cash" not in part["summary"]   # not reported as a FAILED lines-check mismatch


# --- M5: the stock gap is compared on magnitude, and the evidence behind it is recorded ------------------------------


async def test_negative_closing_stock_still_explains_the_tb_row_and_records_the_evidence(tmp_path):
    """A Stock Summary total that exports negative (credit side) must still explain the same gap (abs), and the
    gap / TB debit / TB credit that decided it are recorded."""
    fake, on_action = _fake(tb=TB_WITH_STOCK, stock="-5000.00")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    entry = part["observations"]["tb_vs_rollup"]["Current Assets"]
    assert entry["explained_by_stock"] is True
    assert entry["stock_total"] == Decimal("-5000.00")
    assert entry["stock_gap"] == Decimal("5000.00")
    assert entry["stock_row_debit"] == Decimal("-976437.00")
    assert entry["stock_row_credit"] is None
    assert "Stock Summary" in part["spec_impact"]
