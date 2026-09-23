"""Probe 18 — do TB, Bills and Stock Summary as-on a past date return correct history? (S0 spec §7 "Probe 18", A part)

Feeds decision 11, R30 and Parts 2 + 3. Two sub-verdicts (spec §5.1): TB, and bills/stock; the part outcome is the
worse of the two. The B part (TB as-on 31-03-2023 vs the dataset) comes in plan part 3.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills, parse_ledger_list, parse_trial_balance
from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import (A_FY_FROM, ZERO, amount, ancestors, dmy, is_countable, ledger_movements, master_request,
                             parse_parents, parse_vouchers, primary_lines, qty_number, stock_bearing_groups,
                             stock_rows_any_depth, tally_date, top_group, voucher_request)

TB_AS_ON = "31-10-2025"
BILLS_AS_ON = "30-09-2025"
VOUCHER_FIELDS = ["Date", "VoucherTypeName", "MasterId", "IsCancelled", "IsOptional", "IsPostDated",
                  "AllLedgerEntries", "LedgerEntries", "AllInventoryEntries"]
STOCK_FIELDS = ["Name", "Parent", "BaseUnits", "OpeningBalance"]
STOCK_EXPLODE_CANDIDATE = {"EXPLODEFLAG": "Yes"}      # probe 17's first candidate: items under their stock groups
TB_IMPACT = ("A TB as-on a past date isn't history: there is no valid parity anchor while the backfill is incomplete, "
             "so parity is suspended during the backfill (R30, decision 11).")
BILLS_STOCK_IMPACT = ("Bills Receivable / Payable or Stock Summary as-on a past date aren't history: those tiles lose "
                      "their month-end comparison (Part 1 probe 18, Part 3).")


def tb_verdict(tb_rows: dict[str, Decimal | None], ledgers: dict[str, dict], groups: dict[str, str],
               vouchers: list[dict], as_on: date) -> dict:
    moves = ledger_movements(vouchers, up_to=as_on)
    computed: dict[str, Decimal] = {}
    for name, row in ledgers.items():
        parent = row["parent_group"]
        if parent in ("", "Primary"):
            continue
        top = top_group(parent, groups)
        computed[top] = computed.get(top, ZERO) + (row["opening_balance"] or ZERO) + moves.get(name, ZERO)
    stock_groups = stock_bearing_groups(groups)
    compared: dict[str, dict] = {}
    stock_side: dict[str, dict] = {}
    for group in sorted(set(tb_rows) | {g for g, v in computed.items() if v != ZERO}):
        tb_value, mine = tb_rows.get(group), computed.get(group, ZERO)
        entry = {"tb": tb_value, "computed": mine, "match": (tb_value if tb_value is not None else ZERO) == mine}
        (stock_side if group in stock_groups else compared)[group] = entry
    mismatched = sorted(group for group, entry in compared.items() if not entry["match"])
    return {"verdict": "FAILED" if mismatched or not compared else "CONFIRMED", "groups": compared,
            "stock_bearing": stock_side, "mismatched": mismatched}


def pending_bills(vouchers: list[dict], ledgers: dict[str, dict], groups: dict[str, str], as_on: date,
                  side: str) -> dict[str, Decimal]:
    """'party|bill' → pending on `as_on`, from the bill allocations on party lines (receivable: debtors, payable: creditors)."""
    wanted = "Sundry Debtors" if side == "receivable" else "Sundry Creditors"
    totals: dict[str, Decimal] = {}
    for voucher in vouchers:
        when = tally_date(voucher["header"].get("DATE", ""))
        if not is_countable(voucher) or when is None or when > as_on:
            continue
        for item in primary_lines(voucher):
            party = item["fields"].get("LEDGERNAME", "")
            row = ledgers.get(party)
            if row is None or wanted not in ancestors(row["parent_group"], groups):
                continue
            for bill in item["bills"]:
                value = amount(bill.get("AMOUNT"))
                if value is not None:
                    key = f"{party}|{bill.get('NAME', '')}"
                    totals[key] = totals.get(key, ZERO) + value
    sign = Decimal("-1") if side == "receivable" else Decimal("1")
    return {key: sign * value for key, value in totals.items() if value != ZERO}


def _bills_side(report_text: str, expected: dict[str, Decimal]) -> dict:
    reported = {f"{b['party_name']}|{b['bill_number']}": b["amount"] for b in parse_bills(report_text)}
    return {"reported": reported, "expected": expected, "match": reported == expected,
            "weak": not reported and not expected}


def stock_verdict(rows: list[dict], items: list[dict[str, str]], vouchers: list[dict], as_on: date) -> dict:
    expected = {item["Name"]: qty_number(item["OpeningBalance"]) or ZERO for item in items}
    parent = {item["Name"]: item["Parent"] for item in items}
    for voucher in vouchers:
        when = tally_date(voucher["header"].get("DATE", ""))
        if not is_countable(voucher) or when is None or when > as_on:
            continue
        for inv in voucher["inventory"]:
            name = inv["fields"].get("STOCKITEMNAME", "")
            qty = qty_number(inv["fields"].get("ACTUALQTY", ""))
            if name and qty is not None:
                inward = inv["fields"].get("ISDEEMEDPOSITIVE", "") == "Yes"
                expected[name] = expected.get(name, ZERO) + (abs(qty) if inward else -abs(qty))
    by_group: dict[str, Decimal] = {}
    for name, qty in expected.items():
        by_group[parent.get(name, "")] = by_group.get(parent.get(name, ""), ZERO) + qty
    compared: dict[str, dict] = {}
    for row in rows:
        if row["qty"] is None:
            continue
        if row["name"] in expected:
            want = expected[row["name"]]
        elif row["name"] in by_group:
            want = by_group[row["name"]]
        else:
            continue
        compared[row["name"]] = {"reported": row["qty"], "expected": want, "value": row["value"],
                                 "match": row["qty"] == want}
    mismatches = sorted(name for name, entry in compared.items() if not entry["match"])
    return {"verdict": "CONFIRMED" if compared and not mismatches else "FAILED", "compared": compared,
            "mismatches": mismatches, "item_rows": sum(1 for row in rows if row["name"] in expected),
            "direction_rule": "ISDEEMEDPOSITIVE=Yes is inward"}


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    tb_date, bills_date = dmy(TB_AS_ON), dmy(BILLS_AS_ON)
    tb_rows = {row["account_name"]: row["closing_balance"] for row in parse_trial_balance(
        await ctx.send("tb_asof_2025-10-31", wrap_report("Trial Balance", A_FY_FROM, TB_AS_ON, company)))}
    vouchers = parse_vouchers(await ctx.send("vouchers_to_2025-10-31",
                                             voucher_request("S0P18Vouchers", VOUCHER_FIELDS, company, to_date=TB_AS_ON)))
    ledgers = {row["name"]: row for row in parse_ledger_list(await ctx.send(
        "ledger_list", master_request("S0P18Ledgers", "Ledger", ["Name", "Parent", "OpeningBalance"], company)))}
    groups = parse_parents(await ctx.send("group_list", master_request("S0P18Groups", "Group", ["Name", "Parent"], company)))
    tb = tb_verdict(tb_rows, ledgers, groups, vouchers, tb_date)

    receivable = await ctx.send("bills_receivable_asof_2025-09-30",
                                wrap_report("Bills Receivable", BILLS_AS_ON, BILLS_AS_ON, company))
    payable = await ctx.send("bills_payable_asof_2025-09-30", wrap_report("Bills Payable", BILLS_AS_ON, BILLS_AS_ON, company))
    bills = {"receivable": _bills_side(receivable, pending_bills(vouchers, ledgers, groups, bills_date, "receivable")),
             "payable": _bills_side(payable, pending_bills(vouchers, ledgers, groups, bills_date, "payable"))}
    stock_text = await ctx.send("stock_summary_asof_2025-09-30",
                                wrap_report("Stock Summary", A_FY_FROM, BILLS_AS_ON, company,
                                            extra_vars=STOCK_EXPLODE_CANDIDATE))
    items = read_objects(await ctx.send("stock_item_openings",
                                        master_request("S0P18Stock", "StockItem", STOCK_FIELDS, company)),
                         "STOCKITEM", STOCK_FIELDS)
    stock = stock_verdict(stock_rows_any_depth(stock_text), items, vouchers, bills_date)
    bills_ok = bills["receivable"]["match"] and bills["payable"]["match"]
    sub = {"tb": tb["verdict"], "bills_stock": "CONFIRMED" if bills_ok and stock["verdict"] == "CONFIRMED" else "FAILED"}
    ctx.observe("tb", tb)
    ctx.observe("bills", bills)
    ctx.observe("stock", stock)
    ctx.observe("sub_verdicts", sub)

    problems, impacts = [], []
    if sub["tb"] == "FAILED":
        problems.append(f"TB as-on {TB_AS_ON} ≠ opening + lines for {', '.join(tb['mismatched']) or 'every group'}")
        impacts.append(TB_IMPACT)
    if sub["bills_stock"] == "FAILED":
        wrong = [side for side in ("receivable", "payable") if not bills[side]["match"]]
        what = [f"bills {side}" for side in wrong] + ([f"stock ({', '.join(stock['mismatches']) or 'nothing comparable'})"]
                                                      if stock["verdict"] == "FAILED" else [])
        problems.append(f"as-on {BILLS_AS_ON}: {'; '.join(what)}")
        impacts.append(BILLS_STOCK_IMPACT)
    if problems:
        return PartResult(Outcome.FAILED, "; ".join(problems), spec_impact=" ".join(impacts))
    vacuous_note = " (Bills Receivable check is vacuous: nothing pending on either side)" \
        if bills["receivable"]["weak"] else ""
    return PartResult(Outcome.CONFIRMED, f"TB as-on {TB_AS_ON}, Bills and Stock Summary as-on {BILLS_AS_ON} equal what the "
                                         f"vouchers give (stock values recorded, not compared){vacuous_note}")


PROBE = Probe(
    id=18,
    name="historical_reports",
    question="Do TB, Bills Receivable/Payable and Stock Summary as-on a past date return correct history?",
    feeds=("decision 11", "R30", "Parts 2 + 3"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0, 1),
    educational_sensitive=True,
)
