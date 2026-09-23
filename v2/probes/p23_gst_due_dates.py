"""Probe 23 — GST classification on ledger masters (S0 spec §7 "Probe 23", A part). Feeds the Part 3 GST tile.

The due-date / credit-period half (B part) is added in plan part 3.
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import master_request

GST_CANDIDATES = ["TaxType", "GSTDutyHead", "TypeOfDutyTax"]
FIELDS = ["Name", "Parent", *GST_CANDIDATES]
TAX_PARENT = "Duties & Taxes"
DUTY_HEADS = {"Central Tax", "State Tax", "Integrated Tax"}


async def run_a(ctx: ProbeContext) -> PartResult:
    rows = read_objects(await ctx.send("gst_ledgers", master_request("S0P23Ledgers", "Ledger", FIELDS, ctx.company_name)),
                        "LEDGER", FIELDS)
    tax = [row for row in rows if row["Parent"] == TAX_PARENT]
    other = [row for row in rows if row["Parent"] != TAX_PARENT]
    per_field = {field: {"tax_filled": sum(1 for row in tax if row[field]),
                         "other_filled": sum(1 for row in other if row[field]),
                         "tax_values": sorted({row[field] for row in tax if row[field]}),
                         "other_values": sorted({row[field] for row in other if row[field]})}
                 for field in GST_CANDIDATES}
    rule_field = None
    for field in GST_CANDIDATES:
        tax_values = {row[field] for row in tax}
        if tax and "" not in tax_values and not tax_values & {row[field] for row in other}:
            rule_field = field
            break
    duty_heads = sorted({row["GSTDutyHead"] for row in tax})
    duty_head_ok = bool(tax) and set(duty_heads) <= DUTY_HEADS
    ctx.observe("tax_ledgers", len(tax))
    ctx.observe("fields", per_field)
    ctx.observe("rule_field", rule_field)
    ctx.observe("duty_heads", duty_heads)
    ctx.observe("duty_head_ok", duty_head_ok)
    if rule_field is None:
        return PartResult(Outcome.FAILED, f"No candidate field ({', '.join(GST_CANDIDATES)}) identifies the "
                                          f"{len(tax)} Duties & Taxes ledgers",
                          spec_impact="Tax ledgers can't be identified without name matching: the GST position tile is "
                                      "dropped from v1, never approximated (Part 1 probe 23, Part 3).")
    head = "GSTDutyHead gives Central / State / Integrated Tax" if duty_head_ok else "GSTDutyHead doesn't give the duty head"
    return PartResult(Outcome.CONFIRMED, f"{rule_field} identifies the {len(tax)} GST ledgers "
                                         f"({per_field[rule_field]['tax_values']}); {head}",
                      spec_impact=f"S1 classifies GST ledgers by {rule_field}; "
                                  + ("duty head from GSTDutyHead." if duty_head_ok else "no duty head field (tile shows "
                                                                                        "GST in total only)."))


PROBE = Probe(
    id=23,
    name="gst_due_dates",
    question="Do ledger masters expose GST classification (and bills a due date / credit period)?",
    feeds=("Part 3 tiles",),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
