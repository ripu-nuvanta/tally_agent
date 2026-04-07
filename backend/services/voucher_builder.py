"""Convert ExtractedDocument into Tally voucher payload data.

Handles date format conversion (YYYY-MM-DD → YYYYMMDD), narration building,
and GST entry construction. Output is consumed by TallyWriter.create_payment_voucher().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from backend.services.document_parser import ExtractedDocument


@dataclass
class VoucherData:
    voucher_type: str
    date: str  # YYYYMMDD
    debit_ledger: str
    credit_ledger: str
    amount: Decimal
    narration: str
    gst_entries: list[dict] = field(default_factory=list)


def _convert_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Tally import."""
    return date_str.replace("-", "")


def _build_narration(doc: ExtractedDocument) -> str:
    """Build narration from vendor name and line item descriptions."""
    parts = []
    if doc.vendor_name:
        parts.append(doc.vendor_name)
    descriptions = [item.description for item in doc.line_items if item.description]
    if descriptions:
        parts.append(", ".join(descriptions[:3]))
    return " — ".join(parts) if parts else "Expense entry"


def build_payment_voucher_data(
    doc: ExtractedDocument,
    expense_ledger: str,
    payment_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Payment voucher.

    Args:
        doc: Parsed document data.
        expense_ledger: Tally ledger for the expense (debit side).
        payment_ledger: Cash/Bank ledger (credit side).
        gst_ledgers: Optional dict mapping GST type to ledger name,
            e.g., {"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST", "igst_input": "INPUT IGST"}.
    """
    gst_entries: list[dict] = []
    if doc.gst and gst_ledgers:
        if doc.gst.cgst_amount and "cgst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["cgst_input"],
                "amount": float(doc.gst.cgst_amount),
            })
        if doc.gst.sgst_amount and "sgst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["sgst_input"],
                "amount": float(doc.gst.sgst_amount),
            })
        if doc.gst.igst_amount and "igst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["igst_input"],
                "amount": float(doc.gst.igst_amount),
            })

    return VoucherData(
        voucher_type="Payment",
        date=_convert_date(doc.date),
        debit_ledger=expense_ledger,
        credit_ledger=payment_ledger,
        amount=doc.total_amount,
        narration=_build_narration(doc),
        gst_entries=gst_entries,
    )
