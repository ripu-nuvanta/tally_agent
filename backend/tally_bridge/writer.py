"""Tally write operations — validates and submits import XML.

Wraps import_builder (XML generation) and response_parser (response parsing)
with validation and error handling.

Pre-flight validation runs locally before any Tally call:
- Date present
- Narration present
- At least 2 ledger entries
- Entries balance to zero
- All referenced ledgers exist (when known_ledgers provided)
"""
from __future__ import annotations

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.import_builder import (
    build_cancel_voucher,
    build_create_group,
    build_create_ledger,
    build_create_payment_voucher,
    build_delete_group,
    build_delete_ledger,
    build_delete_voucher,
)
from backend.tally_bridge.response_parser import parse_import_response


class ValidationError(Exception):
    """Raised when voucher data fails dry-run validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


class TallyWriter:
    """Validates and writes vouchers/masters to Tally."""

    def __init__(self, client: TallyClient, company: str):
        self.client = client
        self.company = company

    def validate_voucher(
        self, voucher: dict, known_ledgers: list[str] | None = None,
    ) -> list[str]:
        """Dry-run validation. Returns list of error strings (empty = valid)."""
        errors = []

        if not voucher.get("date"):
            errors.append("Date is required")

        if not voucher.get("narration", "").strip():
            errors.append("Narration is required")

        entries = voucher.get("ledger_entries", [])
        if len(entries) < 2:
            errors.append("At least two ledger entries required")

        # Balance check
        total = sum(e["amount"] for e in entries)
        if abs(total) > 0.01:
            errors.append(f"Ledger entries do not balance (sum={total:.2f})")

        # Ledger existence check
        if known_ledgers is not None:
            known_set = {l.lower() for l in known_ledgers}
            for e in entries:
                if e["ledger"].lower() not in known_set:
                    errors.append(f"Ledger \"{e['ledger']}\" not found in Tally")

        return errors

    async def create_payment_voucher(
        self,
        date: str,
        debit_ledger: str,
        credit_ledger: str,
        amount: float,
        narration: str,
        gst_entries: list[dict] | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Payment voucher in Tally with validation."""
        # Build voucher dict for validation
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": debit_ledger, "amount": -base_amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": -gst["amount"], "is_debit": True})
        entries.append({"ledger": credit_ledger, "amount": amount, "is_debit": False})

        voucher = {
            "voucher_type": "Payment",
            "date": date,
            "narration": narration,
            "ledger_entries": entries,
        }
        errors = self.validate_voucher(voucher, known_ledgers)
        if errors:
            raise ValidationError(errors)

        xml = build_create_payment_voucher(
            date=date,
            debit_ledger=debit_ledger,
            credit_ledger=credit_ledger,
            amount=amount,
            narration=narration,
            company=self.company,
            gst_entries=gst_entries,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_ledger(
        self, name: str, parent: str, gstin: str | None = None,
    ) -> dict:
        """Create a ledger master in Tally."""
        xml = build_create_ledger(name, parent, self.company, gstin)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_group(self, name: str, parent: str) -> dict:
        """Create an account group in Tally."""
        xml = build_create_group(name, parent, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def cancel_voucher(
        self, voucher_type: str, master_id: str, date: str, narration: str = "",
    ) -> dict:
        """Cancel a voucher in Tally (preferred for undo — preserves audit trail)."""
        xml = build_cancel_voucher(voucher_type, master_id, date, self.company, narration)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_voucher(
        self, voucher_type: str, master_id: str, date: str,
    ) -> dict:
        """Delete a voucher from Tally."""
        xml = build_delete_voucher(voucher_type, master_id, date, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_ledger(self, name: str) -> dict:
        """Delete a ledger master from Tally."""
        xml = build_delete_ledger(name, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_group(self, name: str) -> dict:
        """Delete an account group from Tally."""
        xml = build_delete_group(name, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)
