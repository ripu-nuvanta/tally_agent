"""Generate a FRESH batch of test invoice PDFs (unique invoice numbers + content) for
manual upload testing — so they don't trip the duplicate block.

Each run uses a unique tag (timestamp by default), so the invoice numbers and file bytes
differ from any previous batch → neither the file-hash nor the party+invoice-no duplicate
check fires. Parties/items map to the seeded "Bharat Traders" company so they resolve.

Run (PIL is pulled in ad-hoc, no project dependency change):
    uv run --with pillow python scripts/gen_test_invoices.py
    uv run --with pillow python scripts/gen_test_invoices.py --tag MYTAG --outdir ~/Downloads/tally-test-pdfs

Produces 4 PDFs in the outdir: purchase, sales, debit note, credit note.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont


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
    """lines = [(text, font_px), ...] drawn top-to-bottom on a clean white page."""
    img = Image.new("RGB", (1000, 1400), "white")
    d = ImageDraw.Draw(img)
    y = 60
    for text, px in lines:
        d.text((60, y), text, fill="black", font=_font(px))
        y += int(px * 1.7)
    img.save(path, "PDF", resolution=150.0)


def _invoice(doc_title: str, party_label: str, party: str, inv_no: str, date: str,
             items: list[tuple[str, int, int]], gst_rate: int, against: str | None) -> list[tuple[str, int]]:
    base = sum(q * r for _, q, r in items)
    cgst = base * gst_rate / 200
    sgst = base * gst_rate / 200
    total = base + cgst + sgst
    lines: list[tuple[str, int]] = [
        (doc_title, 44),
        (f"Invoice No: {inv_no}        Date: {date}", 26),
        (f"GSTIN: 27AABCB1234C1Z5", 22),
        (f"{party_label}: {party}", 28),
        ("", 10),
    ]
    if against:
        lines.append((f"Against Original Invoice: {against}", 24))
        lines.append(("", 10))
    lines.append(("Item                         Qty      Rate        Amount", 24))
    for name, q, r in items:
        lines.append((f"{name:<26}  {q:>4}   {r:>8,.0f}   {q*r:>10,.0f}", 24))
    lines += [
        ("", 8),
        (f"Subtotal: {base:,.2f}", 24),
        (f"CGST {gst_rate/2:g}%: {cgst:,.2f}     SGST {gst_rate/2:g}%: {sgst:,.2f}", 24),
        (f"TOTAL: Rs. {total:,.2f}", 30),
    ]
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=datetime.now().strftime("%m%d%H%M"),
                    help="unique batch tag woven into invoice numbers (default: timestamp)")
    ap.add_argument("--date", default="15-Jun-2025",
                    help="invoice date, DD-Mon-YYYY (e.g. 15-May-2026). Note dates "
                         "remain 1 day later. Must be within Tally's open period / working date.")
    ap.add_argument("--outdir", default=os.path.expanduser("~/Downloads/tally-test-pdfs"))
    args = ap.parse_args()
    tag = args.tag
    os.makedirs(args.outdir, exist_ok=True)

    pinv = f"PINV-{tag}"
    sinv = f"SINV-{tag}"
    inv_dt = datetime.strptime(args.date, "%d-%b-%Y")
    date = inv_dt.strftime("%d-%b-%Y")
    ndate = (inv_dt.replace(day=inv_dt.day + 1) if inv_dt.day < 28 else inv_dt).strftime("%d-%b-%Y")

    specs = [
        ("purchase_invoice.pdf",
         _invoice("TAX INVOICE", "Supplier", "Bharat Paper Supplies", pinv, date,
                  [("A4 Paper Ream 500 sheets", 12, 280), ("Stapler Heavy Duty", 4, 320)], 12, None)),
        ("sales_invoice.pdf",
         _invoice("TAX INVOICE", "Customer", "Apex Technologies Pvt Ltd", sinv, date,
                  [("Logitech Wireless Mouse", 15, 800), ("HP Laptop 15s", 1, 45000)], 18, None)),
        ("debit_note.pdf",
         _invoice("DEBIT NOTE", "Supplier", "Bharat Paper Supplies", f"DN-{tag}", ndate,
                  [("A4 Paper Ream 500 sheets", 3, 280)], 12, pinv)),
        ("credit_note.pdf",
         _invoice("CREDIT NOTE", "Customer", "Apex Technologies Pvt Ltd", f"CN-{tag}", ndate,
                  [("Logitech Wireless Mouse", 2, 800)], 18, sinv)),
    ]

    print(f"Batch tag: {tag}  ->  {args.outdir}")
    for fname, lines in specs:
        path = os.path.join(args.outdir, fname)
        _render(path, lines)
        size = os.path.getsize(path)
        invno = next(t for t, _ in lines if t.startswith("Invoice No:")).split("Date:")[0].strip()
        print(f"  {fname:<22} {invno:<22} ({size//1024} KB)")
    print("\nUpload these at http://localhost:5173 — fresh invoice numbers, won't dedup.")


if __name__ == "__main__":
    main()
