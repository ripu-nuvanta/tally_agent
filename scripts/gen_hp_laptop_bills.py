"""Generate N DIFFERENT purchase bills for the SAME stock item (HP Laptop 15s, 5 Nos each)
for manual inventory testing — upload them one by one and confirm stock qty increases by 5
each time.

Each bill gets a unique invoice number (tag + index) so neither the file-hash nor the
party+invoice-no duplicate check fires. Supplier "HP India Sales Pvt Ltd" and item
"HP Laptop 15s" both map to the seeded "Bharat Traders" company so they resolve cleanly
(exact stock-item match → no new master created, just a qty increment).

Run (PIL pulled in ad-hoc, no project dependency change):
    uv run --with pillow python scripts/gen_hp_laptop_bills.py
    uv run --with pillow python scripts/gen_hp_laptop_bills.py --count 2 --qty 5 --date 15-Jun-2025
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

SUPPLIER = "HP India Sales Pvt Ltd"   # seeded creditor (GSTIN 27AAAAA0009A1Z5)
ITEM = "HP Laptop 15s"                # default item (override with --item)
GSTIN = "27AAAAA0009A1Z5"             # supplier GSTIN (override with --gstin)
GST_RATE = 18                         # electronics


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _render(path: str, lines: list[tuple[str, int]]) -> None:
    img = Image.new("RGB", (1000, 1400), "white")
    d = ImageDraw.Draw(img)
    y = 60
    for text, px in lines:
        d.text((60, y), text, fill="black", font=_font(px))
        y += int(px * 1.7)
    img.save(path, "PDF", resolution=150.0)


def _bill(inv_no: str, date: str, qty: int, rate: int,
          item: str, supplier: str, gstin: str) -> list[tuple[str, int]]:
    base = qty * rate
    cgst = base * GST_RATE / 200
    sgst = base * GST_RATE / 200
    total = base + cgst + sgst
    return [
        ("TAX INVOICE", 44),
        (f"Invoice No: {inv_no}        Date: {date}", 26),
        (f"GSTIN: {gstin}", 22),
        (f"Supplier: {supplier}", 28),
        ("", 10),
        ("Item                         Qty      Rate        Amount", 24),
        (f"{item:<26}  {qty:>4}   {rate:>8,.0f}   {base:>10,.0f}", 24),
        ("", 8),
        (f"Subtotal: {base:,.2f}", 24),
        (f"CGST {GST_RATE/2:g}%: {cgst:,.2f}     SGST {GST_RATE/2:g}%: {sgst:,.2f}", 24),
        (f"TOTAL: Rs. {total:,.2f}", 30),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=datetime.now().strftime("%m%d%H%M"),
                    help="unique batch tag woven into invoice numbers (default: timestamp)")
    ap.add_argument("--count", type=int, default=2, help="how many different bills to generate")
    ap.add_argument("--qty", type=int, default=5, help="units per bill")
    ap.add_argument("--rate", type=int, default=35000, help="purchase rate per unit")
    ap.add_argument("--item", default=ITEM, help="stock item name on the bill")
    ap.add_argument("--supplier", default=SUPPLIER, help="supplier (party) name")
    ap.add_argument("--gstin", default=GSTIN, help="supplier GSTIN")
    ap.add_argument("--prefix", default="HPL", help="invoice-number prefix")
    ap.add_argument("--fileprefix", default="purchase_hp_laptop", help="output filename prefix")
    ap.add_argument("--date", default="15-Jun-2025",
                    help="invoice date DD-Mon-YYYY; must be within Tally's open/working period")
    ap.add_argument("--outdir", default=os.path.expanduser("~/Downloads/tally-test-pdfs"))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    date = datetime.strptime(args.date, "%d-%b-%Y").strftime("%d-%b-%Y")

    print(f"Batch tag: {args.tag}  ->  {args.outdir}")
    print(f"{args.count} bills x {args.qty} Nos of '{args.item}' from '{args.supplier}' @ {args.rate:,}\n")
    for i in range(1, args.count + 1):
        inv_no = f"{args.prefix}-{args.tag}-{i}"
        fname = f"{args.fileprefix}_{i}.pdf"
        path = os.path.join(args.outdir, fname)
        _render(path, _bill(inv_no, date, args.qty, args.rate, args.item, args.supplier, args.gstin))
        print(f"  {fname:<30} {inv_no:<20} ({os.path.getsize(path)//1024} KB)")

    expected = args.count * args.qty
    print(f"\nUpload these at http://localhost:5173 one at a time.")
    print(f"Each should add {args.qty} Nos -> total +{expected} Nos for '{args.item}' after all {args.count}.")


if __name__ == "__main__":
    main()
