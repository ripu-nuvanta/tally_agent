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
    doc_type: str
    vendor_name: str | None
    date: str
    total_amount: Decimal
    line_items: list[LineItem] = field(default_factory=list)
    gst: GSTBreakdown | None = None
    payment_mode: str | None = None
    raw_text: str | None = None
    confidence: float = 0.0
    currency: str = "INR"


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


def build_vision_prompt() -> str:
    """Build the Claude Vision extraction prompt for expense receipts."""
    return """Analyze this document (expense receipt, invoice, or bill) and extract structured data.

Return ONLY valid JSON with this exact structure:
{
    "doc_type": "expense" | "purchase" | "sale",
    "vendor_name": "string or null",
    "date": "YYYY-MM-DD",
    "total_amount": number,
    "line_items": [
        {
            "description": "string",
            "amount": number,
            "quantity": number or null,
            "rate": number or null
        }
    ],
    "gst": {
        "cgst_rate": number or null,
        "cgst_amount": number or null,
        "sgst_rate": number or null,
        "sgst_amount": number or null,
        "igst_rate": number or null,
        "igst_amount": number or null,
        "gstin": "string or null"
    } or null,
    "payment_mode": "cash" | "bank" | "upi" | "card" | null
}

Rules:
- All amounts in INR as positive numbers.
- Date in YYYY-MM-DD format.
- If GST is not mentioned or not applicable, set gst to null.
- If unsure about a field, set it to null rather than guessing.
- For expenses, doc_type is always "expense".
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

    return ExtractedDocument(
        doc_type=data.get("doc_type", "expense"),
        vendor_name=data.get("vendor_name"),
        date=data.get("date", ""),
        total_amount=_to_decimal(data.get("total_amount")),
        line_items=line_items,
        gst=gst,
        payment_mode=data.get("payment_mode"),
        confidence=0.85,
    )


def validate_extracted_amounts(doc: ExtractedDocument) -> list[str]:
    """Post-extraction arithmetic validation. Returns list of warning strings.

    Never raises — always returns a list. Caller decides whether to surface
    warnings to the user or block the entry.
    """
    warnings = []

    if doc.total_amount == 0:
        warnings.append("Total amount is zero — please verify")

    items_sum = sum((item.amount for item in doc.line_items), Decimal("0"))
    gst_sum = Decimal("0")
    if doc.gst:
        gst_sum += doc.gst.cgst_amount or Decimal("0")
        gst_sum += doc.gst.sgst_amount or Decimal("0")
        gst_sum += doc.gst.igst_amount or Decimal("0")

    expected_total = items_sum + gst_sum
    if abs(expected_total - doc.total_amount) > Decimal("1.00"):
        warnings.append(
            f"Line items ({items_sum}) + GST ({gst_sum}) = {expected_total}, "
            f"but document total is {doc.total_amount} — please verify"
        )

    if doc.gst and doc.line_items:
        base = items_sum
        if doc.gst.cgst_rate and doc.gst.cgst_amount:
            expected_cgst = base * doc.gst.cgst_rate / Decimal("100")
            if abs(expected_cgst - doc.gst.cgst_amount) > Decimal("1.00"):
                warnings.append(
                    f"CGST {doc.gst.cgst_rate}% of {base} should be {expected_cgst}, "
                    f"but extracted {doc.gst.cgst_amount}"
                )

    return warnings
