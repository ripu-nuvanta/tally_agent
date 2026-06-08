"""Convert ExtractedDocument into Tally voucher payload data.

Handles date format conversion (YYYY-MM-DD → YYYYMMDD), narration building,
and GST entry construction. Output is consumed by TallyWriter.create_payment_voucher().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from backend.config import settings
from backend.services.document_parser import ExtractedDocument
from backend.services.fx import parse_default_rates, resolve_fx_rate
from backend.utils.currency_format import format_inr

_TWO_PLACES = Decimal("0.01")


@dataclass
class VoucherData:
    voucher_type: str
    date: str  # YYYYMMDD
    debit_ledger: str
    credit_ledger: str
    amount: Decimal  # posted amount, always in INR
    narration: str
    gst_entries: list[dict] = field(default_factory=list)
    # GST legs in the ORIGINAL (foreign) currency, paired 1:1 with gst_entries
    # by ledger/order. Used by the chat rate-override recompute (T5/T6).
    original_gst_entries: list[dict] = field(default_factory=list)
    original_currency: str = "INR"
    original_amount: Decimal = Decimal("0")  # total in the document's currency
    fx_rate: Decimal = Decimal("1")
    rate_source: str = "inr"  # how the rate was resolved; caller uses it to warn


def _convert_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Tally import."""
    return date_str.replace("-", "")


def _round_inr(amount: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places (half-up), as INR paise."""
    return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _build_narration(doc: ExtractedDocument) -> str:
    """Build narration from vendor name and line item descriptions."""
    parts = []
    if doc.vendor_name:
        parts.append(doc.vendor_name)
    descriptions = [item.description for item in doc.line_items if item.description]
    if descriptions:
        parts.append(", ".join(descriptions[:3]))
    return " — ".join(parts) if parts else "Expense entry"


def _fx_trail(original_currency: str, original_amount: Decimal, rate: Decimal, inr: Decimal) -> str:
    """Build the FX audit trail appended to the narration for non-INR docs.

    Format: ` | FX: USD 100.00 @ ₹83.50 = ₹8,350.00`.
    """
    return (
        f" | FX: {original_currency} {original_amount:.2f}"
        f" @ ₹{rate:.2f} = {format_inr(float(inr))}"
    )


def build_payment_voucher_data(
    doc: ExtractedDocument,
    expense_ledger: str,
    payment_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    override: Decimal | None = None,
    default_rates: dict[str, float] | None = None,
    fallback: float | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Payment voucher.

    This is the single FX conversion point. The posted ``amount`` (and every GST
    leg) is always in INR: ``round(original × rate, 2)``. Rate precedence is
    override > document > per-currency default > global fallback (see
    ``resolve_fx_rate``). For INR documents the rate is 1 and no FX trail is added.

    The resolved rate source is exposed on ``VoucherData.rate_source`` so the
    caller (orchestrator, T6) can emit warnings: ``"default"``/``"fallback"`` →
    "used default rate"; ``"none"`` → "no rate — blocked".

    Args:
        doc: Parsed document data (amounts in ``doc.original_currency``).
        expense_ledger: Tally ledger for the expense (debit side).
        payment_ledger: Cash/Bank ledger (credit side).
        gst_ledgers: Optional dict mapping GST type to ledger name,
            e.g., {"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST", "igst_input": "INPUT IGST"}.
        override: Chat-supplied rate override (highest precedence).
        default_rates: Per-currency defaults. Defaults to parsing
            ``settings.FX_DEFAULT_RATES`` when None.
        fallback: Global fallback rate. Defaults to ``settings.FX_DEFAULT_RATE``
            when None.
    """
    if default_rates is None:
        default_rates = parse_default_rates(settings.FX_DEFAULT_RATES)
    if fallback is None:
        fallback = settings.FX_DEFAULT_RATE

    rate, rate_source = resolve_fx_rate(
        doc.original_currency,
        doc.fx_rate,
        override,
        default_rates=default_rates,
        fallback=fallback,
    )

    def _to_inr(amount: Decimal) -> Decimal:
        return _round_inr(amount * rate)

    gst_entries: list[dict] = []
    original_gst_entries: list[dict] = []
    if doc.gst and gst_ledgers:
        # Each component yields a paired (INR, original-foreign) leg in lockstep.
        _gst_components = [
            ("cgst_input", doc.gst.cgst_amount),
            ("sgst_input", doc.gst.sgst_amount),
            ("igst_input", doc.gst.igst_amount),
        ]
        for key, foreign_amount in _gst_components:
            if foreign_amount and key in gst_ledgers:
                ledger = gst_ledgers[key]
                gst_entries.append({
                    "ledger": ledger,
                    "amount": float(_to_inr(foreign_amount)),
                })
                original_gst_entries.append({
                    "ledger": ledger,
                    "amount": float(foreign_amount),
                })

    original_amount = doc.total_amount
    inr_amount = _to_inr(original_amount)

    narration = _build_narration(doc)
    if doc.original_currency.strip().upper() != "INR":
        narration += _fx_trail(doc.original_currency, original_amount, rate, inr_amount)

    return VoucherData(
        voucher_type="Payment",
        date=_convert_date(doc.date),
        debit_ledger=expense_ledger,
        credit_ledger=payment_ledger,
        amount=inr_amount,
        narration=narration,
        gst_entries=gst_entries,
        original_gst_entries=original_gst_entries,
        original_currency=doc.original_currency,
        original_amount=original_amount,
        fx_rate=rate,
        rate_source=rate_source,
    )
