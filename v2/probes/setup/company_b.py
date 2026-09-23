"""The idempotent company B loader (S0-B spec §4.3). Lists first, creates only what's missing, reads back
every write, and turns anything XML can't set into a pause step naming the object.

Two gaps between this loader and the brief it was built from (flagged loudly here, and in the Task 6 report,
rather than silently worked around — see docs/tally-write-exploration-v4.md and LESSONS §15):

1. `TallyWriter` (v2/probes/setup/writes.py) has no ledger closing-balance / trial-balance read primitive for
   company B — `list_ledgers`/`ledger()` return Name/Parent/Email/AlterID only. The brief's order-of-operations
   step 7 asks for FY-end balances to be "compared against Tally's own TB"; that comparison is not implementable
   without a new read primitive, which is out of this task's scope (only `company_b.py` + its test). `_verify`
   below checks per-FY voucher counts (which the fake and the real Tally XML server both support) and leaves a
   comment marking the balance check as unimplemented rather than faking it.
2. `create_b_voucher` never writes `ISCANCELLED` (its own docstring: "cancelling is not reliably settable on
   import"). So the two cancelled-tag vouchers in the dataset are created as ordinary (non-cancelled) vouchers,
   and their flag-read-back in `_settle_flags` always fails and always becomes a pause step — there is no code
   path that could make it succeed given the current write surface. This is expected, not a bug: it is the
   pause step the brief's step 6 describes ("any flag that did not stick becomes a pause step").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from v2.agent.tally.xml_utils import read_objects
from v2.probes.companies import COMPANIES
from v2.probes.console import ProbeIO
from v2.probes.reads import voucher_request
from v2.probes.setup.company_b_data import (
    SALES_GST_VOUCHER_TYPE,
    Dataset,
    expected_figures,
    fy_label,
    generate,
)
from v2.probes.setup.writes import B_READBACK_FROM, B_READBACK_TO, TallyWriter, check_writable

F2_INSTRUCTION = ("In TallyPrime press F2 and set the working date to 31-03-2026 or later, then press Enter here. "
                  "Vouchers dated after F2 are silently dropped (LESSONS §15 rule 14).")

_TAG_RE = re.compile(r"^\[S0-B:(\d+)\]")
_VOUCHER_LIST_FIELDS = ["MasterId", "Narration", "Date"]
_VOUCHER_FLAG_FIELDS = ["MasterId", "Narration", "IsCancelled", "IsOptional"]
_MASTER_KINDS = ("groups", "units", "items", "ledgers", "vouchers")


class CompanyBLoadError(Exception):
    """The loader can't continue — a prerequisite the operator must fix first."""


@dataclass
class LoadReport:
    created: dict[str, int] = field(default_factory=lambda: {k: 0 for k in _MASTER_KINDS})
    skipped: dict[str, int] = field(default_factory=lambda: {k: 0 for k in _MASTER_KINDS})
    pauses: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def load_company_b(writer: TallyWriter, io: ProbeIO, *, licence: str = "licensed",
                    company: str = COMPANIES["B"]) -> LoadReport:
    check_writable(company)                       # before any request at all
    dataset = generate(licence=licence)
    report = LoadReport()
    _require_voucher_type(writer, io, company, report)
    _load_masters(writer, company, dataset, report)
    _load_openings(writer, io, company, dataset, report)
    io.wait(F2_INSTRUCTION)
    _load_vouchers(writer, company, dataset, report)
    _settle_flags(writer, io, company, dataset, report)
    _verify(writer, company, dataset, report)
    return report


# --- stage 1: preflight -----------------------------------------------------------------------------------------
def _require_voucher_type(writer: TallyWriter, io: ProbeIO, company: str, report: LoadReport) -> None:
    """`Sales - GST` is a custom voucher type; LESSONS §15 rule 4 — a voucher-type CREATE via XML looks successful
    but doesn't change Tally's behaviour, so it can only be created by the operator, in the UI."""
    if SALES_GST_VOUCHER_TYPE in writer.list_voucher_types(company):
        return
    msg = (f"TallyPrime has no voucher type named {SALES_GST_VOUCHER_TYPE!r}. Create it in the UI "
           "(Accounts Info > Voucher Types > Create, parented to Sales) — voucher-type writes via XML look "
           "successful but do not change behaviour (LESSONS §15 rule 4). Then press Enter here.")
    report.pauses.append(msg)
    io.wait(msg)
    if SALES_GST_VOUCHER_TYPE not in writer.list_voucher_types(company):
        raise CompanyBLoadError(
            f"{SALES_GST_VOUCHER_TYPE!r} still missing after the operator pause — cannot continue.")


# --- stage 2: groups -> units -> items -> ledgers ----------------------------------------------------------------
def _load_masters(writer: TallyWriter, company: str, dataset: Dataset, report: LoadReport) -> None:
    existing_groups = writer.list_groups(company)
    for g in dataset.groups:
        if g.name in existing_groups:
            report.skipped["groups"] += 1
        else:
            writer.create_group(company, g.name, g.parent)
            report.created["groups"] += 1

    existing_units = set(writer.list_units(company))
    for u in dataset.units:
        if u.name in existing_units:
            report.skipped["units"] += 1
        else:
            writer.create_unit(company, u.name, base=u.base, conversion=u.conversion)
            report.created["units"] += 1

    existing_items = writer.list_stock_items(company)
    for i in dataset.items:
        if i.name in existing_items:
            report.skipped["items"] += 1
        else:
            writer.create_stock_item(company, i.name, unit=i.unit, hsn=i.hsn,
                                      opening_qty=i.opening_qty, opening_rate=i.opening_rate)
            report.created["items"] += 1

    existing_ledgers = writer.list_ledgers(company)
    for l in dataset.ledgers:
        if l.name in existing_ledgers:
            report.skipped["ledgers"] += 1
        else:
            writer.create_party_ledger(company, l.name, parent=l.parent, bill_wise=l.bill_wise,
                                        opening=l.opening, gstin=l.gstin)
            report.created["ledgers"] += 1


# --- stage 3: opening bill --------------------------------------------------------------------------------------
def _load_openings(writer: TallyWriter, io: ProbeIO, company: str, dataset: Dataset, report: LoadReport) -> None:
    """The opening balance itself is written by `_load_masters` (create_party_ledger's `opening` argument). The
    bill-wise BILL reference tying that opening balance to a named bill (e.g. "Op/2022-001") has no verified
    Op in docs/tally-write-exploration-v4.md, so it is never attempted by XML — this always becomes a pause,
    naming the bill and the ledger, for the operator to confirm (or create) in Bills Receivable."""
    for l in dataset.ledgers:
        if l.opening_bill:
            msg = (f"Opening bill {l.opening_bill!r} for {l.name!r} (₹{l.opening}): the bill-wise opening-balance "
                   "shape is not a verified Op (docs/tally-write-exploration-v4.md) and was not written by XML. "
                   "Confirm the bill appears under Bills Receivable as on 01-04-2022 (create it in the UI if not), "
                   "then press Enter here.")
            report.pauses.append(msg)
            io.wait(msg)


# --- stage 4: vouchers -------------------------------------------------------------------------------------------
def _parse_tag(narration: str) -> int | None:
    match = _TAG_RE.match(narration or "")
    return int(match.group(1)) if match else None


def _read_vouchers(writer: TallyWriter, company: str, fields: list[str]) -> dict[int, dict[str, str]]:
    """Every company-B voucher over its full date window (S0-B spec §4), keyed by its `[S0-B:n]` tag."""
    xml = voucher_request("S0BVouchers", fields, company, from_date=B_READBACK_FROM, to_date=B_READBACK_TO)
    rows = read_objects(writer.post(xml), "VOUCHER", fields)
    out: dict[int, dict[str, str]] = {}
    for row in rows:
        tag = _parse_tag(row.get("Narration", ""))
        if tag is not None:
            out[tag] = row
    return out


def _flag_predated_drift(existing: dict[int, dict[str, str]], dataset: Dataset, report: LoadReport) -> None:
    """A voucher count that is neither 0 (a brand-new company — nothing to flag, this run will create everything)
    nor equal to the expected total (already fully loaded — this run creates nothing) is drift: something that a
    previous run created is now gone from Tally. This run still repairs it below (idempotent by design — see the
    module docstring's point 2 on why a duplicate-safe repair is always attempted), but a repair is exactly the
    kind of thing `report.problems` exists to surface (LESSONS / brief order-of-operations step 7: "the loader
    reports, it does not silently pass") rather than let a silent re-create paper over data loss."""
    expected = expected_figures(dataset)
    pre_by_fy: dict[str, int] = {}
    for row in existing.values():
        d = _parse_tally_date(row.get("Date", ""))
        if d is not None:
            label = fy_label(d)
            pre_by_fy[label] = pre_by_fy.get(label, 0) + 1
    for fy, expected_count in sorted(expected.voucher_count_by_fy.items()):
        pre_count = pre_by_fy.get(fy, 0)
        if 0 < pre_count < expected_count:
            report.problems.append(
                f"FY {fy}: voucher count was {pre_count}/{expected_count} before this run (Tally was missing "
                f"{expected_count - pre_count}) — recreated the gap now; investigate why they went missing.")


def _load_vouchers(writer: TallyWriter, company: str, dataset: Dataset, report: LoadReport) -> None:
    existing = _read_vouchers(writer, company, _VOUCHER_LIST_FIELDS)
    _flag_predated_drift(existing, dataset, report)
    unit_by_item = {i.name: i.unit for i in dataset.items}
    for v in sorted(dataset.vouchers, key=lambda v: (v.date, v.tag)):
        if v.tag in existing:
            report.skipped["vouchers"] += 1
            continue
        lines = [(line.ledger, line.amount, line.deemed_positive) for line in v.lines]
        inventory = [(inv.item, unit_by_item[inv.item], inv.qty, inv.rate, inv.amount) for inv in v.inventory]
        bills = [(b.name, b.bill_type, b.amount, b.credit_period) for b in v.bills]
        writer.create_b_voucher(company, vch_type=v.vch_type, date=v.date.strftime("%Y%m%d"),
                                 narration=v.narration, party=v.party, lines=lines,
                                 inventory=inventory, bills=bills, optional=v.optional)
        report.created["vouchers"] += 1


# --- stage 5: flags that don't stick ------------------------------------------------------------------------------
def _settle_flags(writer: TallyWriter, io: ProbeIO, company: str, dataset: Dataset, report: LoadReport) -> None:
    by_tag = _read_vouchers(writer, company, _VOUCHER_FLAG_FIELDS)
    for v in dataset.vouchers:
        if v.cancelled:
            _settle_one_flag(io, report, by_tag, v.tag, v.narration, "ISCANCELLED", "IsCancelled")
        if v.optional:
            _settle_one_flag(io, report, by_tag, v.tag, v.narration, "ISOPTIONAL", "IsOptional")


def _settle_one_flag(io: ProbeIO, report: LoadReport, by_tag: dict[int, dict[str, str]], tag: int, narration: str,
                      xml_tag: str, read_field: str) -> None:
    row = by_tag.get(tag)
    if row is not None and row.get(read_field) == "Yes":
        return
    msg = (f"[S0-B:{tag}] {narration}: {xml_tag} did not stick on read-back. Set it manually on this voucher in "
           "the Tally UI, then press Enter here.")
    report.pauses.append(msg)
    io.wait(msg)


# --- stage 6: verification -----------------------------------------------------------------------------------------
def _verify(writer: TallyWriter, company: str, dataset: Dataset, report: LoadReport) -> None:
    """Per-FY voucher counts, compared against `expected_figures`. Never raises — see the module docstring for why
    FY-end ledger balances (brief order-of-operations step 7) are not checked here."""
    expected = expected_figures(dataset)
    rows = _read_vouchers(writer, company, _VOUCHER_LIST_FIELDS)
    actual_by_fy: dict[str, int] = {}
    for row in rows.values():
        d = _parse_tally_date(row.get("Date", ""))
        if d is None:
            continue
        label = fy_label(d)
        actual_by_fy[label] = actual_by_fy.get(label, 0) + 1
    for fy, expected_count in sorted(expected.voucher_count_by_fy.items()):
        actual_count = actual_by_fy.get(fy, 0)
        if actual_count != expected_count:
            report.problems.append(
                f"FY {fy}: voucher count mismatch — expected {expected_count}, Tally has {actual_count}")


def _parse_tally_date(text: str) -> date | None:
    cleaned = (text or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return date(int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8]))
    return None
