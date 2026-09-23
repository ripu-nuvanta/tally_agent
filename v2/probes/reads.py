"""Read requests and parsers shared by the company-A probes (probe side only; S2 grows its own in v2/agent/tally/)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

from v2.agent.tally.amounts import AmountParseError, parse_decimal
from v2.agent.tally.envelopes import wrap_collection
from v2.agent.tally.xml_utils import read_objects, sanitize_xml

A_FY_FROM = "01-04-2025"
A_FY_TO = "31-03-2026"
VOUCHER_CHILDOF = "<CHILDOF>$$VchTypeAllVouchers</CHILDOF>"    # without it a Voucher collection has empty bodies (v4)
LEDGER_LISTS = ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST")
INVENTORY_LISTS = ("ALLINVENTORYENTRIES.LIST", "INVENTORYENTRIES.LIST")
POSTING_RULES = ("default", "all_only", "ledger_plus_alloc", "all_plus_alloc")
ZERO = Decimal("0")

# Tally's reserved primary groups and the nature S1 gives each (Part 1 §6 rung 1 needs balance-sheet vs P&L).
PRIMARY_NATURE: dict[str, str] = {
    "Capital Account": "liabilities", "Loans (Liability)": "liabilities", "Current Liabilities": "liabilities",
    "Suspense A/c": "liabilities", "Branch / Divisions": "liabilities",
    "Fixed Assets": "assets", "Investments": "assets", "Current Assets": "assets", "Misc. Expenses (ASSET)": "assets",
    "Sales Accounts": "income", "Direct Incomes": "income", "Indirect Incomes": "income",
    "Purchase Accounts": "expenses", "Direct Expenses": "expenses", "Indirect Expenses": "expenses",
}
PL_PRIMARY_GROUPS = frozenset(group for group, nature in PRIMARY_NATURE.items() if nature in ("income", "expenses"))


# --- requests -------------------------------------------------------------------------------------------------------
def voucher_request(name: str, fields: list[str], company: str, *, from_date: str = A_FY_FROM, to_date: str = A_FY_TO,
                    filters: list[tuple[str, str]] | None = None, extra_collection_xml: str = "") -> str:
    return wrap_collection(name, "Voucher", fields, company, static_vars={"SVFROMDATE": from_date, "SVTODATE": to_date},
                           filters=filters, extra_collection_xml=VOUCHER_CHILDOF + extra_collection_xml)


def master_request(name: str, object_type: str, fields: list[str], company: str, *,
                   static_vars: dict[str, str] | None = None, filters: list[tuple[str, str]] | None = None) -> str:
    return wrap_collection(name, object_type, fields, company, static_vars=static_vars, filters=filters)


# --- values ---------------------------------------------------------------------------------------------------------
def amount(text: str | None) -> Decimal | None:
    """parse_decimal, except that a non-plain amount (e.g. a forex expression) reads as None instead of raising."""
    try:
        return parse_decimal(text)
    except AmountParseError:
        return None


def tally_date(text: str) -> date | None:
    """'20251001', '1-Oct-25', '01-Oct-2025' or '01-10-2025' → a date; anything else → None."""
    cleaned = (text or "").strip()
    for fmt in ("%Y%m%d", "%d-%b-%y", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def dmy(text: str) -> date:
    return datetime.strptime(text, "%d-%m-%Y").date()


def qty_number(text: str) -> Decimal | None:
    """' 25 Nos' → 25; '-2.0000 NOS' → -2; '' → None."""
    parts = (text or "").strip().split()
    return amount(parts[0]) if parts else None


def signed_ui_amount(text: str) -> Decimal | None:
    """A balance typed from the Tally UI: '62,800 Dr' → -62800 (debit negative); '1,000 Cr' → 1000; '' → None."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.endswith(("dr", "cr")):
        value = amount(cleaned[:-2])
        if value is None:
            return None
        return -abs(value) if lowered.endswith("dr") else abs(value)
    return amount(cleaned)


# --- vouchers -------------------------------------------------------------------------------------------------------
def _leaf_fields(element: ET.Element) -> dict[str, str]:
    return {child.tag: (child.text or "").strip() for child in element if len(child) == 0}


def _filled(element: ET.Element, tag: str) -> list[ET.Element]:
    """Direct children named `tag` that hold something (Tally also exports empty placeholder lists)."""
    return [child for child in element if child.tag == tag and len(child) > 0]


def _line(element: ET.Element, list_tag: str) -> dict:
    fields = _leaf_fields(element)
    return {"list": list_tag, "fields": fields, "amount": amount(fields.get("AMOUNT")),
            "amount_raw": fields.get("AMOUNT", ""),
            "bills": [_leaf_fields(bill) for bill in _filled(element, "BILLALLOCATIONS.LIST")]}


def parse_vouchers(raw_xml: str) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    vouchers: list[dict] = []
    for element in root.iter("VOUCHER"):
        if len(element) == 0:
            continue                                   # CMPINFO's <VOUCHER>0</VOUCHER> counter
        lines = [_line(child, tag) for tag in LEDGER_LISTS for child in _filled(element, tag)]
        inventory = [{"fields": _leaf_fields(inv),
                      "accounting": [_line(a, "ACCOUNTINGALLOCATIONS.LIST")
                                     for a in _filled(inv, "ACCOUNTINGALLOCATIONS.LIST")],
                      "batches": [_leaf_fields(b) for b in _filled(inv, "BATCHALLOCATIONS.LIST")]}
                     for tag in INVENTORY_LISTS for inv in _filled(element, tag)]
        vouchers.append({"attrs": dict(element.attrib), "header": _leaf_fields(element), "ledger_lines": lines,
                         "inventory": inventory})
    return vouchers


def primary_lines(voucher: dict) -> list[dict]:
    """The voucher's own ledger lines: ALLLEDGERENTRIES.LIST if it has any, else LEDGERENTRIES.LIST — never both."""
    all_lines = [item for item in voucher["ledger_lines"] if item["list"] == "ALLLEDGERENTRIES.LIST"]
    return all_lines or [item for item in voucher["ledger_lines"] if item["list"] == "LEDGERENTRIES.LIST"]


def postings(voucher: dict, rule: str = "default") -> list[tuple[str, Decimal | None]]:
    """(ledger, amount) per posting. 'default' = primary lines + inventory accounting allocations (probe 6 checks it)."""
    all_lines = [item for item in voucher["ledger_lines"] if item["list"] == "ALLLEDGERENTRIES.LIST"]
    ledger_lines = [item for item in voucher["ledger_lines"] if item["list"] == "LEDGERENTRIES.LIST"]
    allocations = [a for inv in voucher["inventory"] for a in inv["accounting"]]
    chosen = {"default": primary_lines(voucher) + allocations, "all_only": all_lines,
              "ledger_plus_alloc": ledger_lines + allocations, "all_plus_alloc": all_lines + allocations}[rule]
    return [(item["fields"].get("LEDGERNAME", ""), item["amount"]) for item in chosen]


def is_countable(voucher: dict) -> bool:
    """Affects balances: not cancelled, not optional (post-dated vouchers are the caller's choice)."""
    header = voucher["header"]
    return header.get("ISCANCELLED", "No") != "Yes" and header.get("ISOPTIONAL", "No") != "Yes"


def ledger_movements(vouchers: list[dict], *, up_to: date | None = None, before: date | None = None,
                     include_post_dated: bool = False) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for voucher in vouchers:
        if not is_countable(voucher):
            continue
        if not include_post_dated and voucher["header"].get("ISPOSTDATED", "No") == "Yes":
            continue
        when = tally_date(voucher["header"].get("DATE", ""))
        if when is None or (up_to is not None and when > up_to) or (before is not None and when >= before):
            continue
        for ledger, value in postings(voucher):
            if value is not None:
                totals[ledger] = totals.get(ledger, ZERO) + value
    return totals


# --- masters --------------------------------------------------------------------------------------------------------
def parse_parents(raw_xml: str, tag: str = "GROUP") -> dict[str, str]:
    """name → parent for every `tag` object (primary groups have parent '' or 'Primary')."""
    return {row["Name"]: row["Parent"] for row in read_objects(raw_xml, tag, ["Name", "Parent"]) if row["Name"]}


def _is_top(parent: str) -> bool:
    return parent in ("", "Primary")


def ancestors(name: str, parents: dict[str, str]) -> list[str]:
    """[name, parent, grandparent, …] up to the primary group (cycle-safe)."""
    chain = [name]
    while name in parents and not _is_top(parents[name]) and parents[name] not in chain:
        name = parents[name]
        chain.append(name)
    return chain


def top_group(group: str, parents: dict[str, str]) -> str:
    return ancestors(group, parents)[-1]


def stock_bearing_groups(parents: dict[str, str]) -> set[str]:
    """The primary group holding Stock-in-Hand, whose TB row may include closing stock (no ledger carries it)."""
    return {top_group("Stock-in-Hand", parents)} if "Stock-in-Hand" in parents else {"Current Assets"}


# --- report rows at any depth (exploded reports) ---------------------------------------------------------------------
def tb_rows_any_depth(raw_xml: str) -> list[dict]:
    """name, debit, credit, closing for every DSPDISPNAME in document order — flat or nested (exploded TBs)."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict] = []
    current: dict | None = None
    for element in root.iter():
        if element.tag == "DSPDISPNAME":
            current = {"name": (element.text or "").strip(), "debit": None, "credit": None}
            rows.append(current)
        elif current is not None and element.tag == "DSPCLDRAMTA":
            current["debit"] = amount(element.text)
        elif current is not None and element.tag == "DSPCLCRAMTA":
            current["credit"] = amount(element.text)
    for row in rows:
        present = [value for value in (row["debit"], row["credit"]) if value is not None]
        row["closing"] = sum(present, ZERO) if present else None
    return rows


def stock_rows_any_depth(raw_xml: str) -> list[dict]:
    """name, qty text, closing qty and closing value for every DSPDISPNAME in a Stock Summary — flat or exploded."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict] = []
    current: dict | None = None
    for element in root.iter():
        if element.tag == "DSPDISPNAME":
            current = {"name": (element.text or "").strip(), "qty_text": "", "qty": None, "value": None}
            rows.append(current)
        elif current is not None and element.tag == "DSPCLQTY":
            current["qty_text"] = (element.text or "").strip()
            current["qty"] = qty_number(current["qty_text"])
        elif current is not None and element.tag == "DSPCLAMTA":
            current["value"] = amount(element.text)
    return rows
