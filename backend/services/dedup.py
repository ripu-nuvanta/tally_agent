"""Duplicate-invoice detection (Phase 1 Part B).

Two independent, workspace-scoped checks. If either fires, the caller blocks the
write (hard block, no override):

- B1 exact-file: another UploadedFile in the same workspace already has the same
  sha256 content hash → reason "same file".
- B2 business-key (party ledger + supplier-invoice-no), only when an invoice ref
  was extracted:
    (a) a prior written VoucherEntry in the workspace with the same party +
        reference, or
    (b) Tally itself (authoritative) — the party's vouchers whose REFERENCE
        matches the extracted invoice no (catches invoices entered outside the
        app). Tally errors are swallowed (treated as "no match") so a transient
        Tally failure never crashes an upload — B1 + DB B2 still apply.

All queries are scoped to ``workspace_id``.
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select

from backend.db.models import UploadedFile, VoucherEntry
from backend.tally_bridge.queries.vouchers import get_party_vouchers

logger = logging.getLogger(__name__)

# Voucher types whose REFERENCE field can carry a supplier invoice no.
_PARTY_VOUCHER_TYPES = ["Purchase", "Sales", "Debit Note", "Credit Note", "Payment"]


def sha256_bytes(data: bytes) -> str:
    """Return the hex sha256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


async def find_duplicate(
    db,
    client,
    *,
    workspace_id: str,
    content_hash: str,
    party_ledger: str | None,
    invoice_ref: str | None,
    company: str | None = None,
    exclude_file_id: str | None = None,
) -> dict | None:
    """Return a ``{"voucher_no", "date", "reason"}`` descriptor if the upload is a
    duplicate, else None.

    ``exclude_file_id`` lets the caller exclude the just-persisted UploadedFile
    row (its own hash) from the B1 self-match.
    """
    # --- B1: exact-file ---
    if content_hash:
        stmt = select(UploadedFile).where(
            UploadedFile.workspace_id == workspace_id,
            UploadedFile.content_hash == content_hash,
        )
        if exclude_file_id:
            stmt = stmt.where(UploadedFile.id != exclude_file_id)
        match = (await db.execute(stmt)).scalars().first()
        if match is not None:
            # Surface the written voucher linked to that file, if any.
            ve = (await db.execute(
                select(VoucherEntry).where(
                    VoucherEntry.file_id == match.id,
                    VoucherEntry.status == "written",
                )
            )).scalars().first()
            return {
                "voucher_no": (ve.tally_voucher_number if ve else "") or "",
                "date": match.created_at.isoformat() if match.created_at else "",
                "reason": "same file",
            }

    # --- B2: business key (party + invoice ref). Skip if no invoice ref. ---
    if not invoice_ref:
        return None

    # (a) DB: prior written VoucherEntry with same party + reference.
    rows = (await db.execute(
        select(VoucherEntry).where(
            VoucherEntry.workspace_id == workspace_id,
            VoucherEntry.status == "written",
        )
    )).scalars().all()
    for ve in rows:
        data = ve.voucher_data or {}
        if (data.get("party_ledger") == party_ledger
                and data.get("reference") == invoice_ref):
            return {
                "voucher_no": ve.tally_voucher_number or "",
                "date": (data.get("date") or ""),
                "reason": "same invoice no for party",
            }

    # (b) Tally (authoritative). Errors → treat as "no Tally match".
    if party_ledger:
        try:
            vouchers = await get_party_vouchers(
                client, party_ledger, _PARTY_VOUCHER_TYPES, company=company,
            )
        except Exception as exc:  # noqa: BLE001 — never crash the upload on Tally errors
            logger.warning("Tally dedup query failed for %r: %s", party_ledger, exc)
            vouchers = []
        for v in vouchers:
            if v.get("reference") and v.get("reference") == invoice_ref:
                return {
                    "voucher_no": v.get("voucher_number") or "",
                    "date": v.get("date") or "",
                    "reason": "same invoice no for party",
                }

    return None
