"""Probe 3 — voucher IDs and flags can be fetched (S0 spec §7 "Probe 3", A part). Feeds R6, R16.

The B part (cancelled / optional vouchers carry their flags) is added in plan part 3.
"""
from __future__ import annotations

import re

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import voucher_request

FIELDS = ["GUID", "MasterID", "AlterID", "Date", "VoucherTypeName", "VoucherNumber", "Reference", "PartyLedgerName",
          "Narration", "IsCancelled", "IsOptional", "IsPostDated"]
FLAG_CANDIDATES = ("IsCancelled", "IsOptional", "IsPostDated")
EXPECTED_VOUCHERS = 50                                   # the seed company (docs/seed-data-setup.md)
INVOICE_IN_NARRATION = re.compile(r"Invoice #(?P<ref>[SP]\d{3})")


async def run_a(ctx: ProbeContext) -> PartResult:
    rows = read_objects(await ctx.send("vouchers_ids_flags", voucher_request("S0P03Vouchers", FIELDS, ctx.company_name)),
                        "VOUCHER", FIELDS)
    ids = {}
    for key in ("GUID", "MasterID", "AlterID"):
        values = [row[key] for row in rows]
        ids[key] = {"empty": sum(1 for value in values if not value), "duplicates": len(values) - len(set(values))}
    flags = {flag: {"empty": sum(1 for row in rows if not row[flag]), "yes": sum(1 for row in rows if row[flag] == "Yes")}
             for flag in FLAG_CANDIDATES}
    wrong_references = []
    for row in rows:
        if row["VoucherTypeName"] not in ("Sales", "Purchase"):
            continue
        match = INVOICE_IN_NARRATION.search(row["Narration"])
        expected = match.group("ref") if match else ""
        if row["Reference"] != expected:
            wrong_references.append({"narration": row["Narration"], "reference": row["Reference"], "expected": expected})
    ctx.observe("count", len(rows))
    ctx.observe("ids", ids)
    ctx.observe("flags", flags)
    ctx.observe("wrong_references", wrong_references)

    missing_flags = [flag for flag, entry in flags.items() if entry["empty"]]
    bad_ids = [key for key in ("GUID", "MasterID") if ids[key]["empty"] or ids[key]["duplicates"]]
    if ids["AlterID"]["empty"]:
        bad_ids.append("AlterID")
    if missing_flags or bad_ids or not rows:
        problems = ([f"flag(s) {', '.join(missing_flags)} don't export on every voucher"] if missing_flags else []) + \
                   ([f"{', '.join(bad_ids)} empty or duplicated"] if bad_ids else []) + \
                   (["no vouchers came back"] if not rows else [])
        impacts = (["R16 filtering (cancelled / optional / post-dated) is redesigned before S1."] if missing_flags
                   else []) + (["R6: vouchers can't be keyed and change-tracked by GUID / MasterID / AlterID as "
                                "designed; S1's voucher key is revisited."] if bad_ids or not rows else [])
        return PartResult(Outcome.FAILED, "; ".join(problems), spec_impact=" ".join(impacts))
    differences, impacts = [], []
    if len(rows) != EXPECTED_VOUCHERS:
        differences.append(f"{len(rows)} vouchers came back, not {EXPECTED_VOUCHERS}")
        impacts.append("The voucher collection doesn't return exactly the company's vouchers: the extractor's "
                       "completeness check (count vs CMPINFO / AltVchId) is revisited.")
    if wrong_references:
        differences.append(f"Reference ≠ the invoice number on {len(wrong_references)} Sales/Purchase voucher(s)")
        impacts.append("S1 can't take the invoice number from Reference alone; the recorded cases decide the source "
                       "(LESSONS §9).")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, f"{len(rows)} vouchers: GUID / MasterID unique, AlterID present, the three flags "
                                         "export everywhere, Reference = invoice number")


PROBE = Probe(
    id=3,
    name="voucher_ids_flags",
    question="Can voucher GUID / MasterID / AlterID / Reference and the cancelled / optional / post-dated flags be fetched?",
    feeds=("R6", "R16"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
