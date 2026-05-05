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
    build_create_gst_ledger,
    build_create_journal_voucher,
    build_create_ledger,
    build_create_payment_voucher,
    build_create_purchase_voucher,
    build_create_receipt_voucher,
    build_create_sales_voucher,
    build_create_stock_group,
    build_create_stock_item,
    build_create_unit,
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
        """Dry-run validation. Returns list of error strings (empty = valid).

        Never raises — always returns a list. Caller decides whether to abort.
        """
        errors = []

        if not voucher.get("date"):
            errors.append("Date is required")

        if not voucher.get("narration", "").strip():
            errors.append("Narration is required")

        entries = voucher.get("ledger_entries", [])
        if len(entries) < 2:
            errors.append("At least two ledger entries required")

        # Per-entry validation: check for required keys
        valid_entries = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"Entry {i} is not a dict")
                continue
            if "amount" not in entry or entry["amount"] is None:
                errors.append(f"Entry {i} is missing 'amount'")
                continue
            ledger_name = entry.get("ledger")
            if not ledger_name or not str(ledger_name).strip():
                errors.append(f"Entry {i} is missing 'ledger'")
                continue
            valid_entries.append(entry)

        # Balance check (only on valid entries)
        if valid_entries:
            try:
                total = sum(float(e["amount"]) for e in valid_entries)
                if abs(total) > 0.01:
                    errors.append(f"Ledger entries do not balance (sum={total:.2f})")
            except (TypeError, ValueError) as e:
                errors.append(f"Invalid amount in ledger entries: {e}")

        # Ledger existence check (only on valid entries)
        if known_ledgers is not None and valid_entries:
            known_set = {name.lower() for name in known_ledgers}
            for entry in valid_entries:
                if entry["ledger"].lower() not in known_set:
                    errors.append(f"Ledger \"{entry['ledger']}\" not found in Tally")

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
        state: str | None = None, gst_reg_type: str | None = None,
        opening_balance: float | None = None, is_billwise: bool = False,
    ) -> dict:
        """Create a ledger master in Tally."""
        xml = build_create_ledger(
            name, parent, self.company, gstin=gstin, state=state,
            gst_reg_type=gst_reg_type, opening_balance=opening_balance,
            is_billwise=is_billwise,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_unit(self, name: str, formal_name: str) -> dict:
        """Create a unit of measure in Tally."""
        xml = build_create_unit(name, formal_name, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_stock_group(self, name: str, parent: str = "") -> dict:
        """Create a stock group in Tally."""
        xml = build_create_stock_group(name, parent, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_stock_item(
        self, name: str, group: str, uom: str, opening_qty: float,
        opening_rate: float, hsn_code: str, gst_rate: int,
    ) -> dict:
        """Create a stock item in Tally."""
        xml = build_create_stock_item(
            name, group, uom, opening_qty, opening_rate, hsn_code, gst_rate, self.company,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_gst_ledger(self, name: str, duty_head: str) -> dict:
        """Create a GST duty ledger in Tally."""
        xml = build_create_gst_ledger(name, duty_head, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_sales_voucher(
        self, date: str, voucher_number: str, party: str, items: list[tuple],
        narration: str, gst_mode: str = "intra",
    ) -> dict:
        """Create a Sales voucher in Tally."""
        xml = build_create_sales_voucher(
            date, voucher_number, party, items, narration, gst_mode, self.company,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_purchase_voucher(
        self, date: str, voucher_number: str, party: str, items: list[tuple],
        narration: str, gst_mode: str = "intra",
    ) -> dict:
        """Create a Purchase voucher in Tally."""
        xml = build_create_purchase_voucher(
            date, voucher_number, party, items, narration, gst_mode, self.company,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_receipt_voucher(
        self, date: str, voucher_number: str, party: str, bank_ledger: str,
        amount: float, narration: str,
    ) -> dict:
        """Create a Receipt voucher in Tally."""
        xml = build_create_receipt_voucher(
            date, voucher_number, party, bank_ledger, amount, narration, self.company,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_journal_voucher(
        self, date: str, voucher_number: str, debit_ledger: str, credit_ledger: str,
        amount: float, narration: str,
    ) -> dict:
        """Create a Journal voucher in Tally."""
        xml = build_create_journal_voucher(
            date, voucher_number, debit_ledger, credit_ledger, amount, narration, self.company,
        )
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
