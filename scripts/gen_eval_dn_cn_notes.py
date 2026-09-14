"""Generate the eval DEBIT-NOTE + CREDIT-NOTE fixtures
(tests/eval/fixtures/debit_note.png, tests/eval/fixtures/credit_note.png).

Mirrors the visual style of scripts/gen_eval_sales_invoice.py (round, fixed
values; no Desktop/timestamp coupling) but framed as RETURN documents that are
ALWAYS issued BY "Bharat Traders Private Limited" (the eval books/company) to the
counterparty.

This exercises the company-anchoring classifier change:

- DEBIT NOTE = a PURCHASE RETURN issued in our favour. We return goods to a
  SUPPLIER counterparty ("Bharat Paper Supplies"); it reduces what we owe that
  supplier. Vision (anchored to Bharat Traders) must classify it as *debit_note*
  with party = the SUPPLIER, never our own company.

- CREDIT NOTE = a SALES RETURN. A CUSTOMER ("Sunrise Construction Ltd") returns
  goods; it reduces what that customer owes us. Vision must classify it as
  *credit_note* with party = the CUSTOMER, never our own company.

Fixed, round values (deliberately DIFFERENT from the purchase/sales fixtures so a
mis-extraction is unambiguous):

    DEBIT NOTE  : Subtotal 30,000  CGST 9% 2,700  SGST 9% 2,700  TOTAL 35,400
    CREDIT NOTE : Subtotal 10,000  CGST 9%   900  SGST 9%   900  TOTAL 11,800

Run:
    uv run --with pillow python scripts/gen_eval_dn_cn_notes.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

FIXTURES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "eval", "fixtures",
)

# Issuer is ALWAYS our own company for both note types — this is what anchors the
# direction. The counterparty (party_name) differs by note type.
SELLER = "Bharat Traders Private Limited"
SELLER_GSTIN = "27AABCB1234C1ZP"

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


def _render_note(
    out_path: str,
    *,
    title: str,
    note_no: str,
    note_date: str,
    counterparty: str,
    counterparty_gstin: str,
    counterparty_label: str,
    original_ref: str,
    return_blurb: str,
    lines: list[tuple[str, float]],
) -> tuple[float, float, float, float]:
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(img)

    f_title = _font(60, bold=True)
    f_h = _font(34, bold=True)
    f_med = _font(30)
    f_small = _font(26)
    f_big = _font(38, bold=True)

    # Title
    _right(d, RIGHT, 50, title, f_title)
    d.line((LEFT, 130, RIGHT, 130), fill="black", width=3)

    y = 170
    # Issuer = our company. Notes are ALWAYS issued by us -> anchors the direction.
    d.text((LEFT, y), f"Issued By: {SELLER}", fill="black", font=f_h)
    y += 46
    d.text((LEFT, y), f"GSTIN: {SELLER_GSTIN}", fill="black", font=f_small)
    y += 40
    d.text((LEFT, y), "Maharashtra, India", fill="black", font=f_small)
    y += 60

    d.text((LEFT, y), f"Note No: {note_no}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), f"Note Date: {note_date}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), f"Against Original Invoice No: {original_ref}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), return_blurb, fill="black", font=f_small)
    y += 50
    # Counterparty being billed (supplier for DN, customer for CN). party_name MUST
    # be this, never our own company.
    d.text((LEFT, y), f"{counterparty_label}: {counterparty}", fill="black", font=f_med)
    y += 42
    d.text((LEFT, y), f"{counterparty_label} GSTIN: {counterparty_gstin}", fill="black", font=f_small)
    y += 60

    d.line((LEFT, y, RIGHT, y), fill="black", width=2)
    y += 16
    d.text((LEFT, y), "Description", fill="black", font=f_h)
    _right(d, RIGHT, y, "Amount", f_h)
    y += 52
    d.line((LEFT, y, RIGHT, y), fill="black", width=1)
    y += 18

    subtotal = 0.0
    for desc, amt in lines:
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
    d.text((LEFT, y), return_blurb, fill="black", font=f_small)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    return subtotal, cgst, sgst, total


def main() -> None:
    # --- DEBIT NOTE (purchase return — reduces what we owe a supplier) ---
    dn_path = os.path.join(FIXTURES, "debit_note.png")
    dn = _render_note(
        dn_path,
        title="DEBIT NOTE",
        note_no="DN-EVAL-D001",
        note_date="20-Jun-2025",
        counterparty="Bharat Paper Supplies",
        counterparty_gstin="27BPSAA9012P1Z7",
        counterparty_label="Issued To (Supplier)",
        original_ref="BPS-2025-441",
        return_blurb="Debit note for goods returned to supplier (purchase return).",
        lines=[
            ("A4 Paper Carton (returned)", 18000.0),
            ("Box File Pack (returned)", 12000.0),
        ],
    )

    # --- CREDIT NOTE (sales return — reduces what a customer owes us) ---
    cn_path = os.path.join(FIXTURES, "credit_note.png")
    cn = _render_note(
        cn_path,
        title="CREDIT NOTE",
        note_no="CN-EVAL-C001",
        note_date="22-Jun-2025",
        counterparty="Sunrise Construction Ltd",
        counterparty_gstin="27SUNAA5678B1Z3",
        counterparty_label="Issued To (Customer)",
        original_ref="INV-EVAL-S001",
        return_blurb="Credit note for goods returned by customer (sales return).",
        lines=[
            ("Garden Hose 20m (returned)", 10000.0),
        ],
    )

    for label, path, (sub, cgst, sgst, total) in (
        ("DEBIT NOTE ", dn_path, dn),
        ("CREDIT NOTE", cn_path, cn),
    ):
        print(f"Wrote {path}")
        print(f"  {label}  Subtotal={sub:,.2f}  CGST 9%={cgst:,.2f}  "
              f"SGST 9%={sgst:,.2f}  TOTAL={total:,.2f}")


if __name__ == "__main__":
    main()
