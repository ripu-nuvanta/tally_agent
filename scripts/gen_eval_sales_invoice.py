"""Generate the eval SALES-invoice fixture (tests/eval/fixtures/sales_invoice.png).

Mirrors the visual style of the existing purchase_invoice.png but framed as a
SALES invoice ISSUED BY "Bharat Traders Private Limited" (the eval books/company)
to a customer counterparty ("Sunrise Construction Ltd", a Sundry Debtor).

This exercises the company-anchoring classifier change: because the document is
issued BY our company, Vision (anchored to Bharat Traders) must classify it as
*sales* with party = the CUSTOMER, never our own company.

Fixed, round values so the eval scenario can assert exact figures:
    Subtotal 20,000  CGST 9% 1,800  SGST 9% 1,800  TOTAL 23,600

Run:
    uv run --with pillow python scripts/gen_eval_sales_invoice.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "eval", "fixtures", "sales_invoice.png",
)

SELLER = "Bharat Traders Private Limited"
SELLER_GSTIN = "27AABCB1234C1ZP"
CUSTOMER = "Sunrise Construction Ltd"
CUSTOMER_GSTIN = "27SUNAA5678B1Z3"
INVOICE_NO = "INV-EVAL-S001"
INVOICE_DATE = "15-Jun-2025"

LINES = [
    ("A4 Paper Ream (20 pcs)", 8000.0),
    ("Garden Hose 20m (10 pcs)", 6000.0),
    ("Sprinkler Kit (5 sets)", 6000.0),
]

PAGE_W, PAGE_H = 1100, 1500
LEFT = 60
RIGHT = 1040


def _font(size: int, bold: bool = False):
    paths = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _right(d, x_right, y, text, font, fill="black"):
    w = d.textlength(text, font=font)
    d.text((x_right - w, y), text, fill=fill, font=font)


def main() -> None:
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(img)

    f_title = _font(60, bold=True)
    f_h = _font(34, bold=True)
    f_med = _font(30)
    f_small = _font(26)
    f_big = _font(38, bold=True)

    # Title
    _right(d, RIGHT, 50, "TAX INVOICE", f_title)
    d.line((LEFT, 130, RIGHT, 130), fill="black", width=3)

    y = 170
    # Issuer = our company (seller). This is what anchors the direction to SALES.
    d.text((LEFT, y), f"Seller: {SELLER}", fill="black", font=f_h)
    y += 46
    d.text((LEFT, y), f"GSTIN: {SELLER_GSTIN}", fill="black", font=f_small)
    y += 40
    d.text((LEFT, y), "Maharashtra, India", fill="black", font=f_small)
    y += 60

    d.text((LEFT, y), f"Invoice No: {INVOICE_NO}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), f"Invoice Date: {INVOICE_DATE}", fill="black", font=f_med)
    y += 42
    # Counterparty = the customer being billed. party_name MUST be this, not us.
    d.text((LEFT, y), f"Bill To: {CUSTOMER}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), f"Bill To GSTIN: {CUSTOMER_GSTIN}", fill="black", font=f_small)
    y += 60

    d.line((LEFT, y, RIGHT, y), fill="black", width=2)
    y += 16
    d.text((LEFT, y), "Description", fill="black", font=f_h)
    _right(d, RIGHT, y, "Amount", f_h)
    y += 52
    d.line((LEFT, y, RIGHT, y), fill="black", width=1)
    y += 18

    subtotal = 0.0
    for desc, amt in LINES:
        subtotal += amt
        d.text((LEFT, y), desc, fill="black", font=f_med)
        _right(d, RIGHT, y, f"Rs. {amt:,.2f}", f_med)
        y += 48

    y += 10
    d.line((520, y, RIGHT, y), fill="black", width=1)
    y += 16

    cgst = subtotal * 0.09
    sgst = subtotal * 0.09
    total = subtotal + cgst + sgst

    def _kv(label, value, font=f_med):
        nonlocal y
        d.text((540, y), label, fill="black", font=font)
        _right(d, RIGHT, y, value, font)
        y += 44

    _kv("Subtotal", f"Rs. {subtotal:,.2f}")
    _kv("CGST @ 9%", f"Rs. {cgst:,.2f}")
    _kv("SGST @ 9%", f"Rs. {sgst:,.2f}")
    y += 8
    d.line((520, y, RIGHT, y), fill="black", width=2)
    y += 16
    _kv("TOTAL", f"Rs. {total:,.2f}", f_big)

    y += 40
    d.text((LEFT, y), "Payment Terms: Net 30 days", fill="black", font=f_small)
    y += 40
    d.text((LEFT, y), "Thank you for your business.", fill="black", font=f_small)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG")
    print(f"Wrote {OUT}")
    print(f"  Seller (issuer)   : {SELLER}")
    print(f"  Customer (party)  : {CUSTOMER}")
    print(f"  Invoice No / Date : {INVOICE_NO} / {INVOICE_DATE}")
    print(f"  Subtotal          : {subtotal:,.2f}")
    print(f"  CGST 9%           : {cgst:,.2f}")
    print(f"  SGST 9%           : {sgst:,.2f}")
    print(f"  TOTAL             : {total:,.2f}")


if __name__ == "__main__":
    main()
