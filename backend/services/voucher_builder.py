"""Convert ExtractedDocument into Tally voucher payload data.

Handles date format conversion (YYYY-MM-DD → YYYYMMDD), narration building,
and GST entry construction. Output is consumed by TallyWriter.create_payment_voucher().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from backend.config import settings
from backend.services.document_parser import ExtractedDocument
# Shared FX helpers live in fx.py (the lower layer); re-export the rounding +
# trail builders here so the builder path and the chat-override path stay
# identical (Finding 4). ``_round_inr`` / ``_fx_trail`` keep their existing
# names/signatures for call sites in this module.
from backend.services.fx import (
    _fx_trail,
    _round_inr_dec as _round_inr,
    parse_default_rates,
    resolve_fx_rate,
)


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
    # Group B additions (Purchase/Sales/Debit Note/Credit Note).
    party_ledger: str | None = None
    is_party_ledger: bool = False
    bill_reference: str | None = None
    bill_type: str = "New Ref"


def _convert_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Tally import."""
    return date_str.replace("-", "")


def _build_narration(doc: ExtractedDocument) -> str:
    """Build narration from party (vendor/customer) name and line item descriptions."""
    parts = []
    name = doc.party_name or doc.vendor_name
    if name:
        parts.append(name)
    descriptions = [item.description for item in doc.line_items if item.description]
    if descriptions:
        parts.append(", ".join(descriptions[:3]))
    return " — ".join(parts) if parts else "Expense entry"


def _resolve_fx(
    doc: ExtractedDocument,
    override: Decimal | None,
    default_rates: dict[str, float] | None,
    fallback: float | None,
):
    """Resolve the FX rate + return ``(rate, rate_source, to_inr)``.

    Single FX entry point shared by every mapper. ``to_inr`` rounds
    ``amount × rate`` to 2dp INR. Rate precedence is override > document >
    per-currency default > global fallback (see ``resolve_fx_rate``).
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

    return rate, rate_source, _to_inr


def _gst_legs(
    doc: ExtractedDocument,
    gst_ledgers: dict[str, str] | None,
    direction: str,
    to_inr,
) -> tuple[list[dict], list[dict]]:
    """Build INR + original-currency GST legs for a given direction.

    direction: "input" for Purchase/DN, "output" for Sales/CN. Returns
    ``(gst_entries_inr, original_gst_entries)`` paired 1:1 (used by the chat
    rate-override recompute).
    """
    gst_entries: list[dict] = []
    original_gst_entries: list[dict] = []
    if not doc.gst or not gst_ledgers:
        return gst_entries, original_gst_entries

    components = [
        (f"cgst_{direction}", doc.gst.cgst_amount),
        (f"sgst_{direction}", doc.gst.sgst_amount),
        (f"igst_{direction}", doc.gst.igst_amount),
    ]
    for key, foreign_amount in components:
        if foreign_amount and key in gst_ledgers:
            ledger = gst_ledgers[key]
            gst_entries.append({"ledger": ledger, "amount": float(to_inr(foreign_amount))})
            original_gst_entries.append({"ledger": ledger, "amount": float(foreign_amount)})
    return gst_entries, original_gst_entries


def _narration_with_fx(
    doc: ExtractedDocument, original_amount: Decimal, rate: Decimal, inr_amount: Decimal
) -> str:
    """Build narration, appending an FX trail for foreign-currency documents."""
    narration = _build_narration(doc)
    if doc.original_currency.strip().upper() != "INR":
        narration += _fx_trail(doc.original_currency, original_amount, rate, inr_amount)
    return narration


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
    rate, rate_source, to_inr = _resolve_fx(doc, override, default_rates, fallback)
    gst_entries, original_gst_entries = _gst_legs(doc, gst_ledgers, "input", to_inr)

    original_amount = doc.total_amount
    inr_amount = to_inr(original_amount)
    narration = _narration_with_fx(doc, original_amount, rate, inr_amount)

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


def _build_invoice_voucher_data(
    doc: ExtractedDocument,
    voucher_type: str,
    party_ledger: str,
    contra_ledger: str,
    gst_direction: str,
    gst_ledgers: dict[str, str] | None,
    bill_type: str,
    bill_reference: str | None,
    party_on_debit: bool,
    override: Decimal | None,
    default_rates: dict[str, float] | None,
    fallback: float | None,
) -> VoucherData:
    """Shared mapper for Purchase/Sales/Debit Note/Credit Note.

    FX conversion is identical to the payment path: ``amount`` and every GST leg
    are INR. ``debit_ledger``/``credit_ledger`` are populated for the validation
    layer (party on one side, contra ledger on the other) following each
    voucher's polarity. ``party_on_debit`` matches the XML builder convention so
    every layer agrees:
      - party_on_debit=False (Purchase/Credit Note): debit=contra, credit=party.
      - party_on_debit=True  (Sales/Debit Note):     debit=party,  credit=contra.

    Note Debit Note (purchase return) puts the party on DEBIT — the INVERSE of a
    Purchase — so the return reduces the payable; Credit Note (sales return) puts
    the party on CREDIT — the inverse of a Sales — so it reduces the receivable.
    """
    rate, rate_source, to_inr = _resolve_fx(doc, override, default_rates, fallback)
    gst_entries, original_gst_entries = _gst_legs(doc, gst_ledgers, gst_direction, to_inr)

    original_amount = doc.total_amount
    inr_amount = to_inr(original_amount)
    narration = _narration_with_fx(doc, original_amount, rate, inr_amount)

    if party_on_debit:
        debit_ledger, credit_ledger = party_ledger, contra_ledger
    else:
        debit_ledger, credit_ledger = contra_ledger, party_ledger

    return VoucherData(
        voucher_type=voucher_type,
        date=_convert_date(doc.date),
        debit_ledger=debit_ledger,
        credit_ledger=credit_ledger,
        amount=inr_amount,
        narration=narration,
        gst_entries=gst_entries,
        original_gst_entries=original_gst_entries,
        original_currency=doc.original_currency,
        original_amount=original_amount,
        fx_rate=rate,
        rate_source=rate_source,
        party_ledger=party_ledger,
        is_party_ledger=True,
        bill_reference=bill_reference,
        bill_type=bill_type,
    )


def build_purchase_voucher_data(
    doc: ExtractedDocument,
    party_ledger: str,
    purchase_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    override: Decimal | None = None,
    default_rates: dict[str, float] | None = None,
    fallback: float | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Purchase voucher.

    GST is input-side; bill allocation is a fresh ``New Ref``. Amount is INR
    (FX-converted), matching ``build_payment_voucher_data``.
    """
    return _build_invoice_voucher_data(
        doc, voucher_type="Purchase", party_ledger=party_ledger,
        contra_ledger=purchase_ledger, gst_direction="input",
        gst_ledgers=gst_ledgers, bill_type="New Ref", bill_reference=None,
        party_on_debit=False, override=override,
        default_rates=default_rates, fallback=fallback,
    )


def build_sales_voucher_data(
    doc: ExtractedDocument,
    party_ledger: str,
    sales_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    override: Decimal | None = None,
    default_rates: dict[str, float] | None = None,
    fallback: float | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Sales voucher.

    GST is output-side; bill allocation is a fresh ``New Ref``.
    """
    return _build_invoice_voucher_data(
        doc, voucher_type="Sales", party_ledger=party_ledger,
        contra_ledger=sales_ledger, gst_direction="output",
        gst_ledgers=gst_ledgers, bill_type="New Ref", bill_reference=None,
        party_on_debit=True, override=override,
        default_rates=default_rates, fallback=fallback,
    )


def build_debit_note_data(
    doc: ExtractedDocument,
    party_ledger: str,
    purchase_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    original_ref: str | None = None,
    override: Decimal | None = None,
    default_rates: dict[str, float] | None = None,
    fallback: float | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Debit Note.

    A Debit Note is a purchase return: party (supplier) on DEBIT, purchase-
    returns contra on CREDIT (the INVERSE of a Purchase) so the Agst Ref reduces
    the payable. GST is input-side (reversed); bill allocation is ``Agst Ref``
    against the original bill. ``original_ref`` takes precedence; when omitted it
    falls back to ``doc.original_invoice_ref``.
    """
    bill_reference = original_ref or doc.original_invoice_ref
    return _build_invoice_voucher_data(
        doc, voucher_type="Debit Note", party_ledger=party_ledger,
        contra_ledger=purchase_ledger, gst_direction="input",
        gst_ledgers=gst_ledgers, bill_type="Agst Ref",
        bill_reference=bill_reference, party_on_debit=True, override=override,
        default_rates=default_rates, fallback=fallback,
    )


def build_credit_note_data(
    doc: ExtractedDocument,
    party_ledger: str,
    sales_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    original_ref: str | None = None,
    override: Decimal | None = None,
    default_rates: dict[str, float] | None = None,
    fallback: float | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Credit Note.

    A Credit Note is a sales return: party (customer) on CREDIT, sales-returns
    contra on DEBIT (the INVERSE of a Sales) so the Agst Ref reduces the
    receivable. GST is output-side (reversed); bill allocation is ``Agst Ref``
    against the original bill. ``original_ref`` takes precedence; when omitted it
    falls back to ``doc.original_invoice_ref``.
    """
    bill_reference = original_ref or doc.original_invoice_ref
    return _build_invoice_voucher_data(
        doc, voucher_type="Credit Note", party_ledger=party_ledger,
        contra_ledger=sales_ledger, gst_direction="output",
        gst_ledgers=gst_ledgers, bill_type="Agst Ref",
        bill_reference=bill_reference, party_on_debit=False, override=override,
        default_rates=default_rates, fallback=fallback,
    )
