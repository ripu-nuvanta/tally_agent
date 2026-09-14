"""Parse uploaded documents into structured ExtractedDocument data.

Routes by file type: CSV/Excel → structured parser, images/PDF → Claude Vision.
Post-extraction arithmetic validation in Python (no LLM math).

The actual Claude Vision API call lives in the orchestrator pipeline (Task 12).
This module provides the prompt, the response parser, and validation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass
class LineItem:
    description: str
    amount: Decimal
    quantity: Decimal | None = None
    rate: Decimal | None = None
    gst_rate: Decimal | None = None
    gst_amount: Decimal | None = None
    unit: str | None = None  # unit of measure as printed (e.g. "Nos"/"Pcs"/"kg")


@dataclass
class GSTBreakdown:
    cgst_rate: Decimal | None = None
    cgst_amount: Decimal | None = None
    sgst_rate: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_rate: Decimal | None = None
    igst_amount: Decimal | None = None
    gstin: str | None = None


@dataclass
class ExtractedDocument:
    doc_type: str                    # "payment" | "purchase" | "sales" | "debit_note" | "credit_note"
    vendor_name: str | None          # back-compat alias for party_name
    date: str
    total_amount: Decimal
    line_items: list[LineItem] = field(default_factory=list)
    gst: GSTBreakdown | None = None
    payment_mode: str | None = None
    raw_text: str | None = None
    confidence: float = 0.0
    currency: str = "INR"  # DEPRECATED: back-compat alias for original_currency
    original_currency: str = "INR"  # ISO code of the document's printed currency
    fx_rate: Decimal | None = None  # rate printed on the document, if any
    # --- Group B additions ---
    party_name: str | None = None       # canonical: vendor or customer
    original_amount: Decimal = Decimal("0")  # total in the document's currency
    inr_amount: Decimal = Decimal("0")       # total converted to INR (== total when no rate)
    invoice_number: str | None = None        # this document's OWN invoice/bill number
    original_invoice_ref: str | None = None  # DN/CN only: the ORIGINAL invoice being adjusted


_STRUCTURED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ofx"}
_VISION_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def detect_file_type(filename: str, mime_type: str) -> str:
    """Determine parsing strategy from filename/MIME type.

    Returns: "structured", "vision", or "unsupported".
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _STRUCTURED_EXTENSIONS:
        return "structured"
    if ext in _VISION_EXTENSIONS:
        return "vision"
    return "unsupported"


def build_vision_prompt(company_name: str | None = None) -> str:
    """Build the Claude Vision extraction prompt for all document types.

    When ``company_name`` is provided, a "Perspective" block anchors the
    purchase-vs-sales direction to the user's own company (the books being
    kept): a document *issued by* the company is a sale, a document *billed to*
    the company is a purchase, and ``party_name`` is always the counterparty.
    When ``company_name`` is falsy (None/empty), the prompt is unchanged from
    the original framing-based rules (back-compat for legacy/tests).
    """
    perspective = ""
    if company_name:
        perspective = f"""
Perspective (whose books are these?):
- These books belong to "{company_name}". Classify direction from THIS company's point of view.
- If the document was ISSUED BY "{company_name}" (we are the seller / "from" party) → "sales" (or "credit_note" for a sales return).
- If the document is BILLED TO "{company_name}" (we are the buyer — look for a "Bill To" naming "{company_name}") → "purchase" (or "debit_note" for a purchase return; "payment" for an immediately-paid expense).
- "party_name" is ALWAYS the COUNTERPARTY (the other business), NEVER "{company_name}" itself.
"""
    return _vision_prompt_body(perspective)


def _vision_prompt_body(perspective: str) -> str:
    return """Analyze this document (expense receipt, purchase invoice, sales invoice, debit note, or credit note) and extract structured data.

Return ONLY valid JSON with this exact structure:
{
    "doc_type": "payment" | "purchase" | "sales" | "debit_note" | "credit_note",
    "party_name": "vendor or customer name, string or null",
    "date": "YYYY-MM-DD",
    "currency": "ISO code, e.g. USD/EUR/INR (default INR if none shown)",
    "original_currency": "ISO code, e.g. USD/EUR/INR (default INR if none shown)",
    "fx_rate": number or null,
    "total_amount": number,
    "line_items": [
        {
            "description": "string",
            "amount": number,
            "quantity": number or null,
            "rate": number or null,
            "unit": "unit of measure as printed, e.g. Nos/Pcs/kg, or null if not shown"
        }
    ],
    "gst": {
        "cgst_rate": number or null,
        "cgst_amount": number or null,
        "sgst_rate": number or null,
        "sgst_amount": number or null,
        "igst_rate": number or null,
        "igst_amount": number or null,
        "gstin": "vendor/customer GSTIN or null"
    } or null,
    "payment_mode": "cash" | "bank" | "upi" | "card" | null,
    "invoice_number": "string or null (this document's own invoice/bill number, e.g. Invoice No / Bill No / Inv #)",
    "original_invoice_ref": "string or null ((debit/credit notes only) the ORIGINAL invoice being adjusted — NOT this document's own number)"
}

Classification rules:
- "payment": Direct expense paid immediately (petty cash, reimbursement, taxi, food).
- "purchase": Vendor invoice for goods or services on credit (supplier invoice, SaaS subscription).
- "sales": Invoice issued to a customer for goods or services.
- "debit_note": Return or adjustment against a purchase (reduces amount owed to supplier).
- "credit_note": Return or adjustment against a sale (reduces amount owed by customer).
""" + perspective + """
Currency rules:
- Report amounts in the document's ORIGINAL currency exactly as printed. Do NOT convert to INR.
- Amounts as positive numbers.
- "original_currency" (and the back-compat "currency"): the ISO code of the currency shown on the document (e.g. USD, EUR, INR). Default to "INR" if the document shows none.
- "fx_rate": only set this if the document itself prints an exchange rate; otherwise null.

Other rules:
- Date in YYYY-MM-DD format.
- "invoice_number": always set this to THIS document's own invoice/bill number (Invoice No, Bill No, Inv #) for every doc type, if shown; otherwise null.
- "original_invoice_ref": ONLY for debit/credit notes — the ORIGINAL invoice being adjusted/returned. This is NOT this document's own number. Set null for plain invoices and when not shown.
- If GST is not mentioned or not applicable, set gst to null.
- If unsure about a field, set it to null rather than guessing.
- Return ONLY the JSON, no markdown formatting or explanation."""


def _to_decimal(value) -> Decimal:
    """Convert a value to Decimal, handling None and string inputs."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def parse_vision_response(response_text: str) -> ExtractedDocument:
    """Parse Claude Vision's JSON response into ExtractedDocument.

    Tolerates markdown code fences (```json ... ```) that the model may emit
    despite instructions.
    """
    text = response_text.strip()
    if text.startswith("```"):
        # Strip opening fence (with or without language tag)
        first_newline = text.find("\n")
        text = text[first_newline + 1:] if first_newline != -1 else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)

    line_items = []
    for item in data.get("line_items", []) or []:
        line_items.append(LineItem(
            description=item.get("description", ""),
            amount=_to_decimal(item.get("amount")),
            quantity=_to_decimal(item["quantity"]) if item.get("quantity") is not None else None,
            rate=_to_decimal(item["rate"]) if item.get("rate") is not None else None,
            gst_rate=_to_decimal(item["gst_rate"]) if item.get("gst_rate") is not None else None,
            gst_amount=_to_decimal(item["gst_amount"]) if item.get("gst_amount") is not None else None,
            unit=(str(item["unit"]).strip() or None) if item.get("unit") is not None else None,
        ))

    gst = None
    if data.get("gst"):
        g = data["gst"]
        gst = GSTBreakdown(
            cgst_rate=_to_decimal(g["cgst_rate"]) if g.get("cgst_rate") is not None else None,
            cgst_amount=_to_decimal(g["cgst_amount"]) if g.get("cgst_amount") is not None else None,
            sgst_rate=_to_decimal(g["sgst_rate"]) if g.get("sgst_rate") is not None else None,
            sgst_amount=_to_decimal(g["sgst_amount"]) if g.get("sgst_amount") is not None else None,
            igst_rate=_to_decimal(g["igst_rate"]) if g.get("igst_rate") is not None else None,
            igst_amount=_to_decimal(g["igst_amount"]) if g.get("igst_amount") is not None else None,
            gstin=g.get("gstin"),
        )

    # Currency: prefer original_currency (Group B), fall back to legacy currency (Slice A).
    currency_raw = data.get("original_currency") or data.get("currency")
    currency = currency_raw.strip().upper() if currency_raw else "INR"
    fx_rate = _to_decimal(data["fx_rate"]) if data.get("fx_rate") is not None else None

    # party_name is canonical (Group B); vendor_name kept as back-compat alias.
    party_name = data.get("party_name") or data.get("vendor_name")
    total = _to_decimal(data.get("total_amount"))

    # inr_amount: convert when a rate is present for a foreign currency, else == total.
    if fx_rate and currency != "INR":
        inr_amount = total * fx_rate
    else:
        inr_amount = total

    return ExtractedDocument(
        doc_type=data.get("doc_type", "payment"),
        vendor_name=party_name,  # back-compat alias
        party_name=party_name,
        date=data.get("date", ""),
        total_amount=total,
        line_items=line_items,
        gst=gst,
        payment_mode=data.get("payment_mode"),
        confidence=0.85,
        currency=currency,
        original_currency=currency,
        original_amount=total,
        fx_rate=fx_rate,
        inr_amount=inr_amount,
        invoice_number=data.get("invoice_number"),
        original_invoice_ref=data.get("original_invoice_ref"),
    )


def validate_extracted_amounts(doc: ExtractedDocument) -> list[str]:
    """Post-extraction arithmetic validation. Returns list of warning strings.

    Never raises — always returns a list. Caller decides whether to surface
    warnings to the user or block the entry.
    """
    warnings = []
    try:
        total = _to_decimal(doc.total_amount)
        if total == 0:
            warnings.append("Total amount is zero — please verify")

        # FX validation (Group B): flag foreign-currency docs.
        original_currency = (doc.original_currency or "INR").strip().upper()
        if original_currency != "INR":
            if doc.fx_rate is None:
                warnings.append(
                    f"Foreign currency ({original_currency}) with no exchange rate — "
                    "please verify INR amount"
                )
            elif doc.fx_rate > 0:
                original_amount = _to_decimal(doc.original_amount) or total
                expected_inr = original_amount * doc.fx_rate
                inr_amount = _to_decimal(doc.inr_amount)
                if inr_amount and abs(expected_inr - inr_amount) > Decimal("1.00"):
                    warnings.append(
                        f"{original_currency} {original_amount} × {doc.fx_rate} = "
                        f"{expected_inr}, but INR amount is {inr_amount} — please verify"
                    )

        items = doc.line_items or []
        items_sum = sum((_to_decimal(item.amount) for item in items), Decimal("0"))

        gst_sum = Decimal("0")
        if doc.gst:
            gst_sum += _to_decimal(doc.gst.cgst_amount)
            gst_sum += _to_decimal(doc.gst.sgst_amount)
            gst_sum += _to_decimal(doc.gst.igst_amount)

        expected_total = items_sum + gst_sum
        if abs(expected_total - total) > Decimal("1.00"):
            warnings.append(
                f"Line items ({items_sum}) + GST ({gst_sum}) = {expected_total}, "
                f"but document total is {total} — please verify"
            )

        if doc.gst and items:
            base = items_sum
            cgst_rate = _to_decimal(doc.gst.cgst_rate)
            cgst_amount = _to_decimal(doc.gst.cgst_amount)
            if cgst_rate and cgst_amount:
                expected_cgst = base * cgst_rate / Decimal("100")
                if abs(expected_cgst - cgst_amount) > Decimal("1.00"):
                    warnings.append(
                        f"CGST {cgst_rate}% of {base} should be {expected_cgst}, "
                        f"but extracted {cgst_amount}"
                    )
            sgst_rate = _to_decimal(doc.gst.sgst_rate)
            sgst_amount = _to_decimal(doc.gst.sgst_amount)
            if sgst_rate and sgst_amount:
                expected_sgst = base * sgst_rate / Decimal("100")
                if abs(expected_sgst - sgst_amount) > Decimal("1.00"):
                    warnings.append(
                        f"SGST {sgst_rate}% of {base} should be {expected_sgst}, "
                        f"but extracted {sgst_amount}"
                    )
            igst_rate = _to_decimal(doc.gst.igst_rate)
            igst_amount = _to_decimal(doc.gst.igst_amount)
            if igst_rate and igst_amount:
                expected_igst = base * igst_rate / Decimal("100")
                if abs(expected_igst - igst_amount) > Decimal("1.00"):
                    warnings.append(
                        f"IGST {igst_rate}% of {base} should be {expected_igst}, "
                        f"but extracted {igst_amount}"
                    )
    except Exception as e:
        warnings.append(f"Validation error: {type(e).__name__}: {e}")

    return warnings
