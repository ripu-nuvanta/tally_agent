"""Generate MULTI-LINE test invoice PDFs (purchase + sales framings) for the
TallyPrime AI Agent, so Claude Vision can be exercised on direction classification
and multi-line-item extraction.

Each invoice renders a proper line-item table (Item | Qty | Unit | Rate | Amount),
a GST summary (CGST 9% + SGST 9% = 18% on the line subtotal) and a grand total.

Two framings:
- PURCHASE: supplier name + GSTIN prominent at TOP as the issuing vendor; a
  "Bill To: Bharat Traders Private Limited" line. Vision should read doc_type="purchase".
- SALES: "Bharat Traders Private Limited" (seller) at TOP as issuer; a prominent
  "Bill To: <customer>" + customer GSTIN. Vision should read doc_type="sales".

Invoice numbers carry a timestamp-derived tag so re-runs don't collide with the
file-hash / party+invoice-no duplicate checks.

Run (PIL pulled in ad-hoc, no project dependency change):
    uv run --with pillow python scripts/gen_invoice_matrix.py
"""
from __future__ import annotations

import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

OUTDIR = os.path.expanduser("~/Desktop/tally-matrix-test-2026-06-18")
INVOICE_DATE = "21-Jun-2025"
SELLER = "Bharat Traders Private Limited"
SELLER_GSTIN = "27AABCB1234C1ZP"
BUYER = "Bharat Traders Private Limited"  # who WE are in a purchase framing
GST_RATE = 18  # CGST 9% + SGST 9%

# Page / layout geometry
PAGE_W, PAGE_H = 1000, 1400
LEFT = 60
# Table column x-positions (left edge of each column)
COL_ITEM = 60
COL_QTY = 540
COL_UNIT = 620
COL_RATE = 730  # Rate right-aligned to RATE_RIGHT
COL_AMT = 880  # Amount right-aligned to ~960
RATE_RIGHT = 820  # right edge of Rate column (gap before Amount column starts)


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


def _right(d, x_right, y, text, font, fill="black"):
    w = d.textlength(text, font=font)
    d.text((x_right - w, y), text, fill=fill, font=font)


# Each invoice: framing, party, party_gstin, prefix, lines[(desc, qty, unit, rate)]
INVOICES = [
    {
        "fname": "purchase_existinggroup.pdf",
        "framing": "purchase",
        "party": "Aqua Pipes & Fittings Co",
        "party_gstin": "27AAQAA1234A1Z9",
        "prefix": "AQP",
        "suffix": "1",
        "lines": [
            ("HP Laptop 15s", 2, "Nos", 38000),
            ("Copper Pipe 15mm", 50, "Nos", 220),
            ("Pipe Clamp Set", 10, "Box", 150),
        ],
    },
    {
        "fname": "purchase_newgroup.pdf",
        "framing": "purchase",
        "party": "Aqua Pipes & Fittings Co",
        "party_gstin": "27AAQAA1234A1Z9",
        "prefix": "AQP",
        "suffix": "2",
        "lines": [
            ("Water Meter Digital", 5, "Nos", 1200),
            ("Teflon Tape", 100, "Roll", 25),
        ],
    },
    {
        "fname": "sales_existinggroup.pdf",
        "framing": "sales",
        "party": "Sunrise Construction Ltd",
        "party_gstin": "27SUNAA5678B1Z3",
        "prefix": "BT-S",
        "suffix": "1",
        "lines": [
            ("A4 Paper Ream 500 sheets", 10, "Pcs", 350),
            ("Garden Hose 20m", 5, "Pcs", 800),
            ("Sprinkler Kit", 8, "Set", 1200),
        ],
    },
    {
        "fname": "sales_newgroup.pdf",
        "framing": "sales",
        "party": "Sunrise Construction Ltd",
        "party_gstin": "27SUNAA5678B1Z3",
        "prefix": "BT-S",
        "suffix": "2",
        "lines": [
            ("Lawn Mower Manual", 3, "Nos", 4500),
            ("Mulch Mat", 200, "Mtr", 45),
        ],
    },
    {
        "fname": "purchase_newsupplier.pdf",
        "framing": "purchase",
        "party": "Metro Hardware Supplies",
        "party_gstin": "27METRO1234H1Z8",
        "prefix": "MHS",
        "suffix": "1",
        "lines": [
            ("HP Laptop 15s", 1, "Nos", 38000),
            ("Steel Bracket Heavy", 25, "Nos", 180),
            ("Hex Bolt Pack", 40, "Pack", 60),
        ],
    },
    {
        "fname": "purchase_vertex.pdf",
        "framing": "purchase",
        "party": "Vertex Industrial Tools",
        "party_gstin": "27VRTEX9012V1Z6",
        "prefix": "VIT",
        "suffix": "1",
        "lines": [
            ("HP Laptop 15s", 1, "Nos", 38000),
            ("Hydraulic Jack 5T", 4, "Nos", 3200),
            ("Welding Rod Box", 15, "Box", 240),
        ],
    },
    {
        "fname": "sales_newcustomer.pdf",
        "framing": "sales",
        "party": "Skyline Developers Pvt Ltd",
        "party_gstin": "27SKYLN5678D1Z4",
        "prefix": "BT-SK",
        "suffix": "1",
        "lines": [
            ("A4 Paper Ream 500 sheets", 5, "Pcs", 350),
            ("Cement Bag 50kg", 20, "Bag", 420),
        ],
    },
    {
        # CREDIT NOTE: issued BY us (seller) TO a customer, against a SALE return.
        # Vision should classify doc_type="credit_note".
        "fname": "credit_note_skyline.pdf",
        "framing": "sales",
        "title": "CREDIT NOTE",
        "note": "Credit note for goods returned by customer",
        "original_ref": "BT-SK-06191546-1",
        "party": "Skyline Developers Pvt Ltd",
        "party_gstin": "27SKYLN5678D1Z4",
        "prefix": "CN",
        "suffix": "1",
        "lines": [
            ("A4 Paper Ream 500 sheets", 2, "Pcs", 350),
        ],
    },
    {
        # DEBIT NOTE: issued BY us (buyer) TO a supplier, against a PURCHASE return.
        # Vision should classify doc_type="debit_note".
        "fname": "debit_note_vertex.pdf",
        "framing": "purchase",
        "title": "DEBIT NOTE",
        "note": "Debit note for goods returned to supplier",
        "original_ref": "VIT-06191632-1",
        "party": "Vertex Industrial Tools",
        "party_gstin": "27VRTEX9012V1Z6",
        "prefix": "DN",
        "suffix": "1",
        "lines": [
            ("HP Laptop 15s", 1, "Nos", 38000),
        ],
    },
    {
        # PAYMENT: a direct expense paid immediately (taxi fare, cash).
        # This is a CASH RECEIPT issued BY the vendor TO the customer who paid.
        # No "Bill To", no "TAX INVOICE", single service expense line, no inventory.
        # Vision should classify doc_type="payment" with payment_mode="cash".
        "fname": "payment_taxi.pdf",
        "kind": "payment",
        "title": "CASH RECEIPT",
        "party": "City Cab Services",  # vendor / issuer of the receipt
        "payment_mode": "Cash",
        "prefix": "RCP",
        "suffix": "1",
        # Single expense line: description + amount only (no Qty/Unit/Rate framing).
        "expense_desc": "Airport drop - taxi fare",
        "expense_amount": 850.0,
        "gst": False,  # keep simple; no GST on this small fare
    },
]


def _render_payment(inv: dict, tag: str) -> tuple[str, str, float, int]:
    """Render a simple paid cash receipt (single service expense line, no inventory).

    Frames as a receipt issued BY the vendor TO the payer: heading "CASH RECEIPT",
    a clear PAID stamp, a Payment Mode line, one description+amount expense line,
    and a "Received With Thanks" footer. Deliberately omits "Bill To" and
    "TAX INVOICE" so Vision classifies it as a payment, not a purchase/sales.
    """
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(img)

    inv_no = f"{inv['prefix']}-{tag}-{inv['suffix']}"

    f_title = _font(46)
    f_big = _font(30)
    f_med = _font(26)
    f_small = _font(22)

    y = 50

    # --- Issuer (the vendor receiving payment) ---
    d.text((LEFT, y), inv["party"], fill="black", font=f_big)
    y += 44
    d.text((LEFT, y), "Conveyance & Taxi Services", fill="black", font=f_small)
    y += 50

    # --- Title ---
    d.text((LEFT, y), inv["title"], fill="black", font=f_title)
    # PAID stamp, right side
    _right(d, 960, y + 6, "** PAID **", f_big, fill="black")
    y += 70

    # --- Meta ---
    d.text((LEFT, y), f"Receipt No: {inv_no}", fill="black", font=f_med)
    _right(d, 960, y, f"Date: {INVOICE_DATE}", f_med)
    y += 44
    d.text((LEFT, y), f"Payment Mode: {inv['payment_mode']}", fill="black", font=f_med)
    _right(d, 960, y, "Status: PAID", f_med)
    y += 40
    d.text((LEFT, y), "Received from: Customer (paid in full)", fill="black", font=f_small)
    y += 50

    # --- Single expense line (no Qty/Unit/Rate inventory framing) ---
    d.line((LEFT, y, 960, y), fill="black", width=2)
    y += 10
    d.text((COL_ITEM, y), "Description", fill="black", font=f_small)
    _right(d, 960, y, "Amount", f_small)
    y += 34
    d.line((LEFT, y, 960, y), fill="black", width=1)
    y += 14

    amount = float(inv["expense_amount"])
    d.text((COL_ITEM, y), inv["expense_desc"], fill="black", font=f_med)
    _right(d, 960, y, f"{amount:,.2f}", f_med)
    y += 44

    d.line((LEFT, y, 960, y), fill="black", width=1)
    y += 18

    # --- Total (no GST in the simple case) ---
    def _kv(label, value, font=f_med):
        nonlocal y
        _right(d, 760, y, label, font)
        _right(d, 960, y, value, font)
        y += 40

    total = amount
    if inv.get("gst"):
        cgst = amount * 0.025
        sgst = amount * 0.025
        total = amount + cgst + sgst
        _kv("Subtotal:", f"{amount:,.2f}")
        _kv("CGST 2.5%:", f"{cgst:,.2f}")
        _kv("SGST 2.5%:", f"{sgst:,.2f}")
        y += 6
        d.line((640, y, 960, y), fill="black", width=2)
        y += 12
    _kv("TOTAL PAID:", f"Rs. {total:,.2f}", f_big)

    y += 30
    d.text((LEFT, y), "Received with thanks. Amount paid in full.", fill="black", font=f_small)

    path = os.path.join(OUTDIR, inv["fname"])
    img.save(path, "PDF", resolution=150.0)
    return inv_no, inv["party"], total, 1


def _render(inv: dict, tag: str) -> tuple[str, str, float, int]:
    if inv.get("kind") == "payment":
        return _render_payment(inv, tag)

    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    d = ImageDraw.Draw(img)

    inv_no = f"{inv['prefix']}-{tag}-{inv['suffix']}"
    framing = inv["framing"]

    f_title = _font(46)
    f_big = _font(30)
    f_med = _font(26)
    f_small = _font(22)
    f_th = _font(22)

    y = 50

    is_note = "title" in inv  # credit/debit note documents

    # --- Issuer header (top of page) ---
    # Credit & debit notes are ALWAYS issued BY our company (the books being kept):
    # a credit note (sale return) and a debit note (purchase return) both go OUT to
    # the counterparty, so the issuer is the seller/Bharat Traders and the party is
    # the counterparty being billed.
    if is_note:
        issuer, issuer_gstin = SELLER, SELLER_GSTIN
        bill_to, bill_to_gstin = inv["party"], inv["party_gstin"]
    elif framing == "purchase":
        issuer, issuer_gstin = inv["party"], inv["party_gstin"]
        bill_to, bill_to_gstin = BUYER, None
    else:  # sales
        issuer, issuer_gstin = SELLER, SELLER_GSTIN
        bill_to, bill_to_gstin = inv["party"], inv["party_gstin"]

    d.text((LEFT, y), issuer, fill="black", font=f_big)
    y += 44
    d.text((LEFT, y), f"GSTIN: {issuer_gstin}", fill="black", font=f_small)
    y += 50

    # --- Title ---
    d.text((LEFT, y), inv.get("title", "TAX INVOICE"), fill="black", font=f_title)
    y += 70

    # --- Invoice meta ---
    no_label = "Note No" if is_note else "Invoice No"
    d.text((LEFT, y), f"{no_label}: {inv_no}", fill="black", font=f_med)
    _right(d, 960, y, f"Date: {INVOICE_DATE}", f_med)
    y += 44

    # --- Original-invoice reference + return wording (notes only) ---
    if is_note:
        d.text(
            (LEFT, y),
            f"Against Original Invoice No: {inv['original_ref']}",
            fill="black",
            font=f_med,
        )
        y += 40
        d.text((LEFT, y), inv["note"], fill="black", font=f_small)
        y += 40

    # --- Bill To ---
    bill_to_label = "Issued To" if is_note else "Bill To"
    d.text((LEFT, y), f"{bill_to_label}: {bill_to}", fill="black", font=f_med)
    y += 36
    if bill_to_gstin:
        gstin_label = "Issued To GSTIN" if is_note else "Bill To GSTIN"
        d.text((LEFT, y), f"{gstin_label}: {bill_to_gstin}", fill="black", font=f_small)
        y += 36
    y += 16

    # --- Table header ---
    d.line((LEFT, y, 960, y), fill="black", width=2)
    y += 10
    d.text((COL_ITEM, y), "Item", fill="black", font=f_th)
    _right(d, COL_QTY + 60, y, "Qty", f_th)
    d.text((COL_UNIT, y), "Unit", fill="black", font=f_th)
    _right(d, RATE_RIGHT, y, "Rate", f_th)
    _right(d, 960, y, "Amount", f_th)
    y += 34
    d.line((LEFT, y, 960, y), fill="black", width=1)
    y += 12

    # --- Line items ---
    subtotal = 0.0
    for desc, qty, unit, rate in inv["lines"]:
        amount = qty * rate
        subtotal += amount
        d.text((COL_ITEM, y), desc, fill="black", font=f_small)
        _right(d, COL_QTY + 60, y, f"{qty}", f_small)
        d.text((COL_UNIT, y), unit, fill="black", font=f_small)
        _right(d, RATE_RIGHT, y, f"{rate:,.2f}", f_small)
        _right(d, 960, y, f"{amount:,.2f}", f_small)
        y += 38

    y += 6
    d.line((LEFT, y, 960, y), fill="black", width=1)
    y += 18

    # --- GST + total block (right-aligned) ---
    cgst = subtotal * 0.09
    sgst = subtotal * 0.09
    total = subtotal + cgst + sgst

    def _kv(label, value, font=f_med):
        nonlocal y
        _right(d, 760, y, label, font)
        _right(d, 960, y, value, font)
        y += 40

    _kv("Subtotal:", f"{subtotal:,.2f}")
    _kv("CGST 9%:", f"{cgst:,.2f}")
    _kv("SGST 9%:", f"{sgst:,.2f}")
    y += 6
    d.line((640, y, 960, y), fill="black", width=2)
    y += 12
    _kv("GRAND TOTAL:", f"Rs. {total:,.2f}", f_big)

    path = os.path.join(OUTDIR, inv["fname"])
    img.save(path, "PDF", resolution=150.0)
    return inv_no, inv["party"], total, len(inv["lines"])


def main() -> None:
    os.makedirs(OUTDIR, exist_ok=True)
    tag = datetime.now().strftime("%m%d%H%M")
    print(f"Batch tag: {tag}  ->  {OUTDIR}\n")
    for inv in INVOICES:
        inv_no, party, total, n = _render(inv, tag)
        size_kb = os.path.getsize(os.path.join(OUTDIR, inv["fname"])) // 1024
        kind = inv.get("framing", inv.get("kind", ""))
        print(
            f"  {inv['fname']:<28} {kind:<9} "
            f"party={party:<28} inv={inv_no:<16} "
            f"lines={n} total=Rs.{total:,.2f} ({size_kb} KB)"
        )


if __name__ == "__main__":
    main()
