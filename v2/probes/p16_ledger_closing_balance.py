"""Probe 16 — does LEDGER.ClosingBalance hold Tally's own ledger balance? (S0 spec §7 "Probe 16", A part)

Feeds decision 11, R30 and Part 2 Rule 1 (Part 1 §6 rung 1). The B part (OpeningBalance scope, as-on 31-03-2023)
comes in plan part 3, so the probe stays PARTIAL until then.
"""
from __future__ import annotations

from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_ledger_list, parse_stock_summary, parse_trial_balance
from v2.probes.actions import Action
from v2.probes.anchors import SEED_PAYABLE, SEED_RECEIVABLE
from v2.probes.companies import THROWAWAY_DATE, THROWAWAY_DATE_TEXT, THROWAWAY_EXPENSE_LEDGER
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.p01_company_counters import LAST_VOUCHER_DATE_BASELINE
from v2.probes.reads import (A_FY_FROM, A_FY_TO, PL_PRIMARY_GROUPS, ZERO, ancestors, dmy, ledger_movements,
                             master_request, parse_parents, parse_vouchers, postings, signed_ui_amount,
                             stock_bearing_groups, top_group, voucher_request)

LEDGER_FIELDS = ["Name", "Parent", "GUID", "OpeningBalance", "ClosingBalance"]
VOUCHER_FIELDS = ["Date", "VoucherTypeName", "MasterId", "Narration", "IsCancelled", "IsOptional", "IsPostDated",
                  "AllLedgerEntries", "LedgerEntries", "AllInventoryEntries"]
THROWAWAY_FIELDS = ["Date", "MasterId", "Narration", "IsPostDated"]
UI_LEDGERS = ("Apex Technologies Pvt Ltd", "HP India Sales Pvt Ltd", "HDFC Bank - Current A/c")
AS_ON_FROM, AS_ON_TO = "01-10-2025", "31-10-2025"
CASH = "Cash"
FUTURE_REF, POST_DATED_REF = "p16-future", "p16-post-dated"
FUTURE_NARRATION = "S0-throwaway 16 future"
POST_DATED_NARRATION = "S0-throwaway 16 post-dated"
# The throwaway "future" voucher is dated 31-03-2026 — company A's period end. It can only separate "as of the period
# end" from "as of Tally's current (F2) date" while the F2 date is BEFORE it; books that already reach that date mean
# Tally opened the company on it, so both readings would include the voucher and the step decides nothing.
FUTURE_CUTOFF = THROWAWAY_DATE
RERUN_HINT = ("run `uv run --project v2 python -m v2.probes reset-a`, then re-run probe 1 and probe 16 on the fresh "
              "copy (`run 1 --company A --rerun`, then `run 16 --company A --rerun`)")
FAILED_IMPACT = ("LEDGER.ClosingBalance isn't Tally's ledger balance: rung 1 collapses to group level, month-bisect "
                 "becomes the main localiser, and Part 2 Rule 1 falls back to group-level forward computation "
                 "(decision 11, Part 1 §16).")


def _ledgers_request(company: str, static_vars: dict[str, str] | None = None) -> str:
    return master_request("S0P16Ledgers", "Ledger", LEDGER_FIELDS, company, static_vars=static_vars)


def _balances(text: str) -> dict[str, dict]:
    return {row["name"]: row for row in parse_ledger_list(text)}


def _value(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def _kinds(ledgers: dict[str, dict], groups: dict[str, str]) -> dict[str, str]:
    """ledger → 'bs' | 'pl' | 'special' (the Profit & Loss A/c sits directly under Primary)."""
    kinds: dict[str, str] = {}
    for name, row in ledgers.items():
        parent = row["parent_group"]
        if parent in ("", "Primary"):
            kinds[name] = "special"
        else:
            kinds[name] = "pl" if top_group(parent, groups) in PL_PRIMARY_GROUPS else "bs"
    return kinds


def _nominal(ledgers: dict[str, dict], kinds: dict[str, str]) -> dict:
    zero, empty, nonzero = [], [], {}
    for name, kind in sorted(kinds.items()):
        if kind != "pl":
            continue
        closing = ledgers[name]["closing_balance"]
        if closing is None:
            empty.append(name)
        elif closing == ZERO:
            zero.append(name)
        else:
            nonzero[name] = closing
    return {"zero": zero, "empty": empty, "nonzero": nonzero}


def _lines_check(ledgers: dict[str, dict], kinds: dict[str, str],
                 movements: dict[str, Decimal]) -> tuple[dict[str, dict], list[str]]:
    """Balance-sheet ledgers whose ClosingBalance ≠ OpeningBalance + Σ lines; and those exported empty for zero."""
    bad: dict[str, dict] = {}
    empty_for_zero: list[str] = []
    for name, kind in sorted(kinds.items()):
        if kind != "bs":
            continue
        closing = ledgers[name]["closing_balance"]
        computed = _value(ledgers[name]["opening_balance"]) + movements.get(name, ZERO)
        if closing is None and computed == ZERO:
            empty_for_zero.append(name)
        elif closing != computed:
            bad[name] = {"closing": closing, "computed": computed}
    return bad, empty_for_zero


def _group_compare(ledgers: dict[str, dict], kinds: dict[str, str], groups: dict[str, str],
                   tb_rows: dict[str, dict], stock_total: Decimal | None) -> dict[str, dict]:
    rollups: dict[str, Decimal] = {}
    for name, kind in kinds.items():
        if kind == "bs":
            top = top_group(ledgers[name]["parent_group"], groups)
            rollups[top] = rollups.get(top, ZERO) + _value(ledgers[name]["closing_balance"])
    stock_groups = stock_bearing_groups(groups)
    result: dict[str, dict] = {}
    for group in sorted(set(rollups) | {g for g in tb_rows if g not in PL_PRIMARY_GROUPS}):
        row = tb_rows.get(group)
        tb, rollup = row["closing_balance"] if row else None, rollups.get(group, ZERO)
        entry: dict = {"tb": tb, "rollup": rollup, "match": _value(tb) == rollup}
        if not entry["match"] and group in stock_groups and tb is not None and stock_total is not None:
            gap = abs(tb - rollup)
            entry["stock_total"] = stock_total
            entry["stock_gap"] = gap
            entry["stock_row_debit"] = row.get("debit_amount") if row else None
            entry["stock_row_credit"] = row.get("credit_amount") if row else None
            entry["explained_by_stock"] = gap == abs(stock_total)
        result[group] = entry
    return result


def _party_totals(ledgers: dict[str, dict], groups: dict[str, str]) -> tuple[Decimal, Decimal]:
    debtors = creditors = ZERO
    for row in ledgers.values():
        if row["parent_group"] in ("", "Primary"):
            continue
        chain = ancestors(row["parent_group"], groups)
        if "Sundry Debtors" in chain:
            debtors += _value(row["closing_balance"])
        elif "Sundry Creditors" in chain:
            creditors += _value(row["closing_balance"])
    return debtors, creditors


def _ui_compare(ctx: ProbeContext, ledgers: dict[str, dict]) -> dict[str, dict]:
    ui: dict[str, dict] = {}
    for name in UI_LEDGERS:
        typed = ctx.ask(f"In Tally, open ledger {name!r} (Display More Reports → Account Books → Ledger) and type the "
                        f"closing balance it shows, e.g. '62,800.00 Dr' — or press Enter to skip:",
                        Action("ui_closing_balance", {"ledger": name}))
        value = signed_ui_amount(typed)
        closing = ledgers.get(name, {}).get("closing_balance")
        ui[name] = {"typed": typed, "ui": value, "closing": closing,
                    "match": None if value is None else value == closing}
    return ui


async def _as_on(ctx: ProbeContext, ledgers: dict[str, dict], kinds: dict[str, str], vouchers: list[dict]) -> dict:
    company = ctx.company_name
    up_to = ledger_movements(vouchers, up_to=dmy(AS_ON_TO))
    before = ledger_movements(vouchers, before=dmy(AS_ON_FROM))
    as_of = _balances(await ctx.send("ledgers_asof_2025-10-31",
                                     _ledgers_request(company, {"SVFROMDATE": A_FY_FROM, "SVTODATE": AS_ON_TO})))
    ranged = _balances(await ctx.send("ledgers_from_2025-10-01",
                                      _ledgers_request(company, {"SVFROMDATE": AS_ON_FROM, "SVTODATE": AS_ON_TO})))
    bs = [name for name, kind in kinds.items() if kind == "bs"]

    def opening(name: str) -> Decimal:
        return _value(ledgers[name]["opening_balance"])

    closing_ok = all(_value(as_of.get(n, {}).get("closing_balance")) == opening(n) + up_to.get(n, ZERO) for n in bs)
    closing_changed = any(as_of.get(n, {}).get("closing_balance") != ledgers[n]["closing_balance"] for n in bs)
    opening_ok = all(_value(ranged.get(n, {}).get("opening_balance")) == opening(n) + before.get(n, ZERO) for n in bs)
    opening_changed = any(_value(ranged.get(n, {}).get("opening_balance")) != opening(n) for n in bs)
    return {"closing_follows_svtodate": closing_ok and closing_changed, "closing_matches_lines": closing_ok,
            "closing_changed": closing_changed, "opening_follows_svfromdate": opening_ok and opening_changed,
            "opening_matches_lines": opening_ok, "opening_changed": opening_changed}


def _as_on_note(as_on: dict) -> str:
    if as_on["opening_follows_svfromdate"]:
        return ("As-on works: OpeningBalance follows SVFROMDATE, so per-ledger opening anchors exist during the "
                "backfill without probe 17 (decision 11).")
    if as_on["closing_follows_svtodate"]:
        return ("As-on closing works (ClosingBalance follows SVTODATE) but OpeningBalance ignores SVFROMDATE: per-ledger "
                "anchors use the as-on closing of the day before the window (decision 11).")
    return ("As-on reading doesn't work (the period variables are ignored): per-ledger anchors during the backfill "
            "depend on probe 17 (decision 11).")


async def _throwaway(ctx: ProbeContext, *, ref: str, narration: str, post_dated: bool, step: str, ledger_step: str,
                     cash_before: Decimal | None) -> dict:
    company = ctx.company_name
    note = f"Delete the voucher with narration {narration!r} if it still exists"
    ctx.on_abort(note)
    kind = "marked post-dated (Ctrl+T on the voucher screen)" if post_dated else "an ordinary (not post-dated) voucher"
    ctx.pause(f"Create a Payment voucher dated {THROWAWAY_DATE_TEXT}, {kind}: Cash → {THROWAWAY_EXPENSE_LEDGER}, ₹1, "
              f"narration {narration!r}. Save it. (company: {company!r})",
              Action("create_voucher", {"company": company, "ref": ref, "ledger": THROWAWAY_EXPENSE_LEDGER,
                                        "amount": "1.00", "narration": narration, "post_dated": post_dated}))
    found = [v for v in parse_vouchers(await ctx.send(step, voucher_request("S0P16Throwaway", THROWAWAY_FIELDS, company)))
             if v["header"].get("NARRATION") == narration]
    after = _balances(await ctx.send(ledger_step, _ledgers_request(company)))
    cash_after = after.get(CASH, {}).get("closing_balance")
    ctx.pause(f"Delete the voucher with narration {narration!r} (open it, Alt+D). (company: {company!r})",
              Action("delete_voucher", {"company": company, "ref": ref}))
    ctx.resolve_abort(note)
    return {"found": bool(found), "is_post_dated_exported": found[0]["header"].get("ISPOSTDATED", "") if found else "",
            "cash_before": cash_before, "cash_after": cash_after, "included_in_closing": cash_after != cash_before}


def books_reach_before_run(ctx: ProbeContext, own_reading: str) -> dict:
    """How far company A's books reached BEFORE this run wrote anything — the F2-date discriminator.

    Tally fixes its current (F2) date when the company opens, so books that stopped short of 31-03-2026 mean the F2
    date is short of it too, and the throwaway voucher really is future data. Probe 16's OWN LastVoucherDate reading
    can't say that: probe 1 runs immediately before it (probe 16 needs the counters request probe 1 confirms) and its
    own 31-03-2026 throwaway leaves LastVoucherDate at 20260331 for good — it does not roll back when the voucher is
    deleted (probe 1, live 2026-09-22). Probe 1's recorded baseline is taken before that voucher, so it is the reading
    to use; probe 16's own reading is only a fallback, and being at or after the true reach it can make this check
    stricter, never looser.
    """
    part = (ctx.store.probe_entry(1) or {}).get("parts", {}).get("A") or {}
    recorded = (part.get("observations") or {}).get(LAST_VOUCHER_DATE_BASELINE)
    if isinstance(recorded, dict):
        value = recorded.get("value") or ""
        if value and recorded.get("available"):
            return {"value": value, "available": True, "source": "probe 1's baseline, before its throwaway voucher"}
        return {"value": "", "available": False,
                "source": "not available: probe 1 recorded no LastVoucherDate for this company"}
    if own_reading:
        return {"value": own_reading, "available": True,
                "source": "probe 16's own reading — probe 1 recorded no baseline, so this may already include this "
                          "run's throwaway vouchers"}
    return {"value": "", "available": False, "source": "not available: LastVoucherDate isn't exported"}


def as_of_verdict(future: dict, reach: dict) -> tuple[str, str]:
    """(verdict, sentence) for "ClosingBalance is as of …". Never decides what the run can't tell apart."""
    if not future["included_in_closing"]:
        # Sound whatever the F2 date is: a balance as of the period end would contain a voucher dated on it.
        return "current_date", (f"Tally's current date (F2), not the period end — the throwaway voucher dated "
                                f"{THROWAWAY_DATE_TEXT}, the period end itself, stayed out of ClosingBalance")
    if reach["available"] and reach["value"] < FUTURE_CUTOFF:
        return "period_end", (f"the period end ({A_FY_TO}), not Tally's current date — the books reached only "
                              f"{reach['value']} before this run, so Tally's current date is before "
                              f"{THROWAWAY_DATE_TEXT} and the throwaway voucher was future data it still counted")
    detail = (f"the books already reached {reach['value']} before this run ({reach['source']})"
              if reach["available"] else f"the pre-run LastVoucherDate is {reach['source']}")
    return "inconclusive", (f"inconclusive: the throwaway voucher dated {THROWAWAY_DATE_TEXT} is in ClosingBalance, but "
                            f"{detail}, so Tally's current date may be on that date too and the two readings can't be "
                            f"told apart. To settle it, {RERUN_HINT}")


def _rule(future: dict, post_dated: dict, as_of: str) -> str:
    if not post_dated["found"]:
        pd = "the post-dated voucher wasn't found after the create, so the post-dated rule is still open"
    elif post_dated["is_post_dated_exported"] != "Yes":
        pd = (f"IsPostDated exported {post_dated['is_post_dated_exported'] or '(empty)'!r}, not 'Yes': the flag didn't "
              "stick, so the post-dated rule is still open")
    else:
        pd = f"post-dated vouchers are {'included' if post_dated['included_in_closing'] else 'excluded'}; IsPostDated exported 'Yes'"
    return f"Rung 1 rule (Part 1 §6): ClosingBalance is as of {as_of}; {pd}."


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    last_voucher_date = (await ctx.counters()).get("LastVoucherDate", "")
    ctx.observe("last_voucher_date", last_voucher_date)
    ledgers = _balances(await ctx.send("ledgers", _ledgers_request(company)))
    if not ledgers:
        return PartResult(Outcome.BLOCKED, "The Ledger collection came back empty — is company A open?")
    groups = parse_parents(await ctx.send("groups", master_request("S0P16Groups", "Group", ["Name", "Parent"], company)))
    vouchers = parse_vouchers(await ctx.send("vouchers_fy", voucher_request("S0P16Vouchers", VOUCHER_FIELDS, company)))
    tb_rows = {row["account_name"]: row for row in parse_trial_balance(
        await ctx.send("tb_fy_end", wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, company)))}
    stock_values = [row["closing_value"] for row in parse_stock_summary(
        await ctx.send("stock_summary_fy_end", wrap_report("Stock Summary", A_FY_FROM, A_FY_TO, company)))]
    stock_total = sum((v for v in stock_values if v is not None), ZERO) if stock_values else None

    kinds = _kinds(ledgers, groups)
    nominal = _nominal(ledgers, kinds)
    bad_lines, empty_for_zero = _lines_check(ledgers, kinds, ledger_movements(vouchers))
    unbalanced_vouchers = [v for v in vouchers if sum((amt for _, amt in postings(v) if amt is not None), ZERO) != ZERO]
    group_cmp = _group_compare(ledgers, kinds, groups, tb_rows, stock_total)
    debtors, creditors = _party_totals(ledgers, groups)
    ctx.observe("ledger_kinds", {k: sum(1 for v in kinds.values() if v == k) for k in ("bs", "pl", "special")})
    ctx.observe("nominal", nominal)
    ctx.observe("closing_vs_lines", {"mismatches": bad_lines, "empty_closing_for_zero": empty_for_zero,
                                     "vouchers": len(vouchers)})
    ctx.observe("unbalanced_vouchers", [v["header"].get("MASTERID", "") for v in unbalanced_vouchers])
    ctx.observe("tb_vs_rollup", group_cmp)
    ctx.observe("party_totals", {"debtors": debtors, "creditors": creditors})
    ctx.observe("special_ledgers", {n: ledgers[n]["closing_balance"] for n, k in kinds.items() if k == "special"})

    ui = _ui_compare(ctx, ledgers)
    ctx.observe("ui_compare", ui)
    as_on = await _as_on(ctx, ledgers, kinds, vouchers)
    ctx.observe("as_on", as_on)
    cash_before = ledgers.get(CASH, {}).get("closing_balance")
    future = await _throwaway(ctx, ref=FUTURE_REF, narration=FUTURE_NARRATION, post_dated=False, step="future_voucher",
                              ledger_step="ledgers_with_future_voucher", cash_before=cash_before)
    post_dated = await _throwaway(ctx, ref=POST_DATED_REF, narration=POST_DATED_NARRATION, post_dated=True,
                                  step="post_dated_voucher", ledger_step="ledgers_with_post_dated",
                                  cash_before=cash_before)
    ctx.observe("future_voucher", future)
    ctx.observe("post_dated_voucher", post_dated)
    reach = books_reach_before_run(ctx, last_voucher_date)
    verdict, as_of = as_of_verdict(future, reach)
    ctx.observe("as_of_basis", {"verdict": verdict, "books_reach_before_run": reach["value"],
                                "available": reach["available"], "source": reach["source"]})
    rule, as_on_note = _rule(future, post_dated, as_of), _as_on_note(as_on)

    failures: list[str] = []
    if bad_lines and not unbalanced_vouchers:
        failures.append(f"ClosingBalance ≠ opening + Σ lines for {len(bad_lines)} balance-sheet ledger(s) "
                        f"({', '.join(sorted(bad_lines)[:5])})")
    if -debtors != SEED_RECEIVABLE:
        failures.append(f"Σ debtors {-debtors} ≠ the Bills Receivable anchor {SEED_RECEIVABLE}")
    if creditors != SEED_PAYABLE:
        failures.append(f"Σ creditors {creditors} ≠ the Bills Payable anchor {SEED_PAYABLE}")
    ui_bad = sorted(name for name, entry in ui.items() if entry["match"] is False)
    if ui_bad:
        failures.append(f"the Tally UI shows another balance for {', '.join(ui_bad)}")
    if failures:
        return PartResult(Outcome.FAILED, "; ".join(failures), spec_impact=f"{FAILED_IMPACT} {rule} {as_on_note}")

    differences: list[str] = []
    impacts: list[str] = []
    if bad_lines and unbalanced_vouchers:
        differences.append(f"{len(unbalanced_vouchers)} voucher(s) don't balance under postings(), so the lines check "
                           f"for {len(bad_lines)} balance-sheet ledger(s) is inconclusive")
        impacts.append("posting rule unverified (probe 6 decides); lines check inconclusive")
    if nominal["nonzero"]:
        differences.append(f"{len(nominal['nonzero'])} nominal ledger(s) have a non-zero ClosingBalance")
        impacts.append("Rung 1 picks balance-sheet ledgers by group nature, never by 'ClosingBalance = 0' (Part 1 §6).")
    mismatched = sorted(group for group, entry in group_cmp.items() if not entry["match"])
    by_stock = [group for group in mismatched if group_cmp[group].get("explained_by_stock")]
    other = [group for group in mismatched if group not in by_stock]
    if by_stock:
        differences.append(f"TB row(s) {', '.join(by_stock)} = ledger rollup ± closing stock")
        impacts.append("Rung 2 adds the Stock Summary closing value to the stock-bearing group before comparing with "
                       "the TB row (Part 1 §6).")
    if other:
        differences.append(f"TB row(s) {', '.join(other)} ≠ ledger rollup")
        impacts.append("Rung 2's group rollup doesn't reproduce these TB rows; the recorded per-group figures decide the "
                       "comparison rule before S1 (Part 1 §6).")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join([*impacts, rule, as_on_note]))
    ui_note = "" if any(entry["match"] is not None for entry in ui.values()) else \
        " (UI balances not read — automated or skipped; a later manual check)"
    return PartResult(Outcome.CONFIRMED, "ClosingBalance = opening + Σ lines for every balance-sheet ledger; debtors and "
                                         "creditors match the anchors; TB rows = ledger rollup" + ui_note,
                      spec_impact=f"{rule} {as_on_note}")


PROBE = Probe(
    id=16,
    name="ledger_closing_balance",
    question="Does LEDGER.ClosingBalance equal Tally's own balances (lines, TB, UI)? Nominal = 0? As-on? As-of date and "
             "post-dated vouchers?",
    feeds=("decision 11", "R30", "Part 2 Rule 1"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0, 1, 2),
    mutating=True,
    educational_sensitive=True,
)
