"""Probe 25 — group nature / revenue flags and voucher-type base type (S0 spec §7 "Probe 25", A part).

Feeds the S1 schema, R5 and R16. The B part (custom voucher type "Sales - GST" → Sales) is added in plan part 3.
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import PL_PRIMARY_GROUPS, PRIMARY_NATURE, ancestors, master_request

GROUP_CANDIDATES = ["PrimaryGroup", "_PrimaryGroup", "Nature", "IsRevenue", "AffectsGrossProfit", "IsDeemedPositive",
                    "ReservedName"]
GROUP_FIELDS = ["Name", "Parent", *GROUP_CANDIDATES]
VOUCHER_TYPE_CANDIDATES = ["Parent", "ReservedName"]
VOUCHER_TYPE_FIELDS = ["Name", *VOUCHER_TYPE_CANDIDATES]
CHECK_GROUP = "National Creditors"


def nature_from_fields(row: dict[str, str]) -> tuple[str | None, str | None]:
    """(nature, the field that gave it) from the candidate fields alone."""
    for field in ("PrimaryGroup", "_PrimaryGroup"):
        if row.get(field) in PRIMARY_NATURE:
            return PRIMARY_NATURE[row[field]], field
    nature = row.get("Nature", "").lower()
    for word, value in (("liabilit", "liabilities"), ("asset", "assets"), ("income", "income"), ("expense", "expenses")):
        if word in nature:
            return value, "Nature"
    return None, None


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    groups = read_objects(await ctx.send("groups", master_request("S0P25Groups", "Group", GROUP_FIELDS, company)),
                          "GROUP", GROUP_FIELDS)
    vtypes = read_objects(await ctx.send("voucher_types", master_request("S0P25VoucherTypes", "VoucherType",
                                                                         VOUCHER_TYPE_FIELDS, company)),
                          "VOUCHERTYPE", VOUCHER_TYPE_FIELDS)
    parents = {row["Name"]: row["Parent"] for row in groups if row["Name"]}
    present = {field: sum(1 for row in groups if row[field]) for field in ["Parent", *GROUP_CANDIDATES]}
    check = next((row for row in groups if row["Name"] == CHECK_GROUP), None)
    walk = ancestors(CHECK_GROUP, parents) if check else []
    walk_nature = PRIMARY_NATURE.get(walk[-1]) if walk else None
    field_nature, nature_field = nature_from_fields(check) if check else (None, None)
    revenue = {row["Name"]: row["IsRevenue"] for row in groups if row["Name"] in PRIMARY_NATURE and row["IsRevenue"]}
    revenue_ok = bool(revenue) and all((value == "Yes") == (name in PL_PRIMARY_GROUPS) for name, value in revenue.items())
    vparents = {row["Name"]: row["Parent"] for row in vtypes if row["Name"]}
    base_types = {row["Name"]: row["ReservedName"] or ancestors(row["Name"], vparents)[-1] for row in vtypes}
    vtypes_ok = bool(vtypes) and all(row["Parent"] or row["ReservedName"] for row in vtypes)
    ctx.observe("present", present)
    ctx.observe("walk", walk)
    ctx.observe("walk_nature", walk_nature)
    ctx.observe("field_nature", field_nature)
    ctx.observe("nature_field", nature_field)
    ctx.observe("is_revenue_consistent", revenue_ok)
    ctx.observe("voucher_type_fields", {field: sum(1 for row in vtypes if row[field]) for field in VOUCHER_TYPE_CANDIDATES})
    ctx.observe("base_types", base_types)

    if not present["Parent"] or check is None or walk_nature != "liabilities":
        return PartResult(Outcome.FAILED, f"Group Parent doesn't classify {CHECK_GROUP!r} (walk: {walk or 'none'})",
                          spec_impact="S1 can't tell balance-sheet from P&L groups from the export: the S1 schema's "
                                      "group classification is revisited before S1 (R5, R16).")
    if field_nature == "liabilities" and revenue_ok and vtypes_ok:
        return PartResult(Outcome.CONFIRMED, f"{nature_field} gives {CHECK_GROUP!r} = liabilities; IsRevenue is "
                                             "consistent; voucher types export Parent / ReservedName",
                          spec_impact=f"S1: group nature from {nature_field}, P&L flag from IsRevenue; voucher base type "
                                      "from ReservedName, walking Parent for custom types.")
    return PartResult(Outcome.DIFFERENT, "Nature / revenue / base-type fields don't all export; walking Parent gives "
                                         f"{CHECK_GROUP!r} → {walk[-1]} ({walk_nature})",
                      spec_impact="Nature is derived by walking Parent to a reserved primary group (PRIMARY_NATURE map) "
                                  "and base type by the voucher-type Parent chain; the mapping goes into the S1 spec.")


PROBE = Probe(
    id=25,
    name="masters_classification",
    question="Do groups export nature / IsRevenue / AffectsGrossProfit, and voucher types their parent and base type?",
    feeds=("S1 schema", "R5", "R16"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
