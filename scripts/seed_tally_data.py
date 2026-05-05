#!/usr/bin/env python3
"""Seed a fresh Tally company with the Bharat Traders dataset.

PREREQUISITE: An empty company "Bharat Traders Private Limited" must already exist
in Tally UI (Create-Company has no documented import envelope). FY 2025-04-01 to
2026-03-31, Maharashtra, GSTIN 27AABCB1234F1ZP, GST registration Regular,
no company-default GST rate.

⚠ ONE-SHOT per company. Per docs/tally-write-exploration-v4.md, once any master is
referenced by a voucher, Tally permanently locks it. To iterate, restore from a
fresh backup or recreate the company.

Usage:
    PYTHONPATH=. python scripts/seed_tally_data.py \\
        --host localhost --port 9000 \\
        --company "Bharat Traders Private Limited"
    # add --dry-run to print XML without POSTing
    # add --phases groups,units,stock_groups,gst_ledgers,ledgers,stock_items,vouchers
    #   to run a subset (default: all phases in this order)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Iterable

import re

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyResponseError
from backend.tally_bridge.writer import TallyWriter
from scripts.seed_data import bharat_traders as bt

async def _tally_current_date(client: TallyClient, company: str) -> str:
    """Query Tally's internal 'current date' (the F2 date). Returns YYYYMMDD."""
    xml = (
        '<ENVELOPE>'
        '<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>'
        '<TYPE>Function</TYPE><ID>$$CurrentDate</ID></HEADER>'
        f'<BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>'
        '</STATICVARIABLES></DESC></BODY></ENVELOPE>'
    )
    raw = await client.post_xml(xml)
    # Response shape: <RESPONSE><RESULT>DD-MM-YYYY</RESULT>...</RESPONSE>
    m = re.search(r"<RESULT>\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*</RESULT>", raw)
    if not m:
        raise RuntimeError(f"Couldn't parse Tally current date from: {raw[:200]!r}")
    dd, mm, yyyy = m.groups()
    return f"{int(yyyy):04d}{int(mm):02d}{int(dd):02d}"


async def _preflight_check(client: TallyClient, company: str) -> None:
    """Halt early if Tally's current date is earlier than the seed's latest
    voucher date. Otherwise vouchers silently drop with a misleading
    'Voucher date is missing' error (license-clamp behavior)."""
    latest = max(
        [v[1] for v in bt.SALES_INVOICES]
        + [v[1] for v in bt.PURCHASE_INVOICES]
        + [v[1] for v in bt.PAYMENTS]
        + [v[1] for v in bt.RECEIPTS]
    )
    current = await _tally_current_date(client, company)
    print(f"Pre-flight: Tally current date = {current}, latest seed voucher = {latest}")
    if current < latest:
        raise RuntimeError(
            f"Tally's current date ({current}) is earlier than the latest seed "
            f"voucher date ({latest}). Vouchers after {current} would silently "
            "drop. Fix: at Gateway of Tally, press F2 and set the current date "
            f"to {latest} or later, then retry."
        )


OFFICE_SUPPLY_ITEMS = {
    "A4 Paper Ream 500 sheets", "Whiteboard Marker Set",
    "Stapler Heavy Duty", "Box File Pack of 10", "Pen Drive 32GB",
}
PHASES_DEFAULT = ["groups", "units", "stock_groups", "gst_ledgers", "ledgers", "stock_items", "vouchers"]


def _sales_ledger(item_name: str) -> str:
    return "Sales - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Sales - Electronics"


def _purchase_ledger(item_name: str) -> str:
    return "Purchase - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Purchase - Electronics"


def _item_meta() -> dict[str, dict]:
    """Build {name: {uom, hsn, gst_rate}} lookup from STOCK_ITEMS."""
    return {
        name: {"uom": uom, "hsn": hsn, "gst_rate": gst}
        for name, _grp, uom, _sell, _oq, _or, _ov, hsn, gst in bt.STOCK_ITEMS
    }


def _build_voucher_items(
    invoice_lines: list[tuple], meta: dict, ledger_fn,
) -> list[tuple]:
    """Convert (item_name, qty, rate) list into builder tuple format."""
    return [
        (name, qty, rate, ledger_fn(name), meta[name]["uom"], meta[name]["gst_rate"])
        for name, qty, rate in invoice_lines
    ]


async def _phase_groups(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Groups ({len(bt.GROUPS)}) ===")
    for name, parent in bt.GROUPS:
        print(f"  + {name} (parent: {parent})")
        if not dry_run:
            await writer.create_group(name=name, parent=parent)


async def _phase_units(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Units ({len(bt.UNITS)}) ===")
    for name, formal in bt.UNITS:
        print(f"  + {name} ({formal})")
        if not dry_run:
            await writer.create_unit(name=name, formal_name=formal)


async def _phase_stock_groups(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Stock Groups ({len(bt.STOCK_GROUPS)}) ===")
    for name, parent in bt.STOCK_GROUPS:
        print(f"  + {name}")
        if not dry_run:
            await writer.create_stock_group(name=name, parent=parent)


async def _phase_gst_ledgers(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: GST Ledgers ({len(bt.GST_LEDGERS)}) ===")
    for name, duty_head in bt.GST_LEDGERS:
        print(f"  + {name} ({duty_head})")
        if not dry_run:
            await writer.create_gst_ledger(name=name, duty_head=duty_head)


async def _phase_ledgers(writer: TallyWriter, dry_run: bool):
    # Skip:
    # - GST ledgers (parent "Duties & Taxes"): handled by _phase_gst_ledgers
    #   which emits TAXTYPE/GSTDUTYHEAD.
    # - "Cash": ships by default in Tally; recreating fails. Opening balance
    #   stays 0 in the seeded company (set manually if needed).
    plain_ledgers = [
        l for l in bt.LEDGERS
        if l[1] != "Duties & Taxes" and l[0] != "Cash"
    ]
    print(f"\n=== Phase: Ledgers ({len(plain_ledgers)}) ===")
    for name, parent, opening, state, gstin, gst_reg in plain_ledgers:
        is_billwise = parent in (
            "North Zone Debtors", "South Zone Debtors",
            "National Creditors", "Local Creditors",
        )
        print(f"  + {name} (parent: {parent}, opening: {opening})")
        if not dry_run:
            await writer.create_ledger(
                name=name, parent=parent, gstin=gstin, state=state,
                gst_reg_type=gst_reg, opening_balance=opening if opening else None,
                is_billwise=is_billwise,
            )


async def _phase_stock_items(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Stock Items ({len(bt.STOCK_ITEMS)}) ===")
    for name, group, uom, _sell_rate, open_qty, open_rate, _open_val, hsn, gst_rate in bt.STOCK_ITEMS:
        print(f"  + {name} (HSN {hsn}, GST {gst_rate}%)")
        if not dry_run:
            await writer.create_stock_item(
                name=name, group=group, uom=uom,
                opening_qty=open_qty, opening_rate=open_rate,
                hsn_code=hsn, gst_rate=gst_rate,
            )


async def _phase_vouchers(writer: TallyWriter, dry_run: bool):
    meta = _item_meta()

    # Combine all vouchers with a sort key (date) so chronological order is preserved.
    sales = [("S", v) for v in bt.SALES_INVOICES]
    purchases = [("P", v) for v in bt.PURCHASE_INVOICES]
    payments = [("PMT", v) for v in bt.PAYMENTS]
    receipts = [("R", v) for v in bt.RECEIPTS]
    all_vouchers = sales + purchases + payments + receipts
    all_vouchers.sort(key=lambda x: x[1][1])  # date is index 1 in every tuple

    print(f"\n=== Phase: Vouchers ({len(all_vouchers)}) ===")
    for kind, v in all_vouchers:
        if kind == "S":
            vnum, date, party, lines, _total, narration = v
            items = _build_voucher_items(lines, meta, _sales_ledger)
            print(f"  + Sales {vnum} {date} {party} ({len(lines)} lines)")
            if not dry_run:
                await writer.create_sales_voucher(
                    date=date, voucher_number=vnum, party=party,
                    items=items, narration=narration, gst_mode="intra",
                )
        elif kind == "P":
            vnum, date, party, lines, _total, narration = v
            items = _build_voucher_items(lines, meta, _purchase_ledger)
            print(f"  + Purchase {vnum} {date} {party} ({len(lines)} lines)")
            if not dry_run:
                await writer.create_purchase_voucher(
                    date=date, voucher_number=vnum, party=party,
                    items=items, narration=narration, gst_mode="intra",
                )
        elif kind == "PMT":
            vnum, date, payee, bank, amount, narration = v
            print(f"  + Payment {vnum} {date} {payee} ₹{amount}")
            if not dry_run:
                # Payment = debit payee, credit bank
                await writer.create_payment_voucher(
                    date=date, debit_ledger=payee, credit_ledger=bank,
                    amount=amount, narration=narration,
                )
        elif kind == "R":
            vnum, date, party, bank, amount, narration = v
            print(f"  + Receipt {vnum} {date} {party} ₹{amount}")
            if not dry_run:
                await writer.create_receipt_voucher(
                    date=date, voucher_number=vnum, party=party,
                    bank_ledger=bank, amount=amount, narration=narration,
                )


PHASE_FNS = {
    "groups": _phase_groups,
    "units": _phase_units,
    "stock_groups": _phase_stock_groups,
    "gst_ledgers": _phase_gst_ledgers,
    "ledgers": _phase_ledgers,
    "stock_items": _phase_stock_items,
    "vouchers": _phase_vouchers,
}


async def run(host: str, port: int, company: str, phases: list[str], dry_run: bool):
    client = TallyClient(host=host, port=port)
    writer = TallyWriter(client=client, company=company)

    print(f"Seeding {company} @ {host}:{port}")
    if dry_run:
        print("(DRY-RUN — no POST)\n")

    if "vouchers" in phases and not dry_run:
        await _preflight_check(client, company)

    for phase in phases:
        if phase not in PHASE_FNS:
            print(f"  unknown phase: {phase}", file=sys.stderr)
            sys.exit(2)
        try:
            await PHASE_FNS[phase](writer, dry_run)
        except TallyResponseError as e:
            print(f"\n!! TallyResponseError in phase {phase}: {e}", file=sys.stderr)
            print("   Stopping. Inspect Tally UI before re-running.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n!! Unexpected error in phase {phase}: {e!r}", file=sys.stderr)
            sys.exit(1)

    print("\nDone.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--company", default=bt.COMPANY_NAME)
    p.add_argument("--phases", default=",".join(PHASES_DEFAULT),
                   help=f"comma-sep subset of {PHASES_DEFAULT}")
    p.add_argument("--dry-run", action="store_true",
                   help="build + log XML, do not POST")
    args = p.parse_args()
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    asyncio.run(run(args.host, args.port, args.company, phases, args.dry_run))


if __name__ == "__main__":
    main()
