"""Tests for Tally writer — validation and write orchestration."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.tally_bridge.writer import TallyWriter, ValidationError


class TestDryRunValidation:
    def test_valid_payment_passes(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test expense",
            "ledger_entries": [
                {"ledger": "Travel Expenses", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel Expenses", "Cash"])
        assert errors == []

    def test_unbalanced_amounts_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Bad entry",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 400.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("balance" in e.lower() for e in errors)

    def test_unknown_ledger_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Unknown Ledger", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Cash"])
        assert any("Unknown Ledger" in e for e in errors)

    def test_missing_narration_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("narration" in e.lower() for e in errors)

    def test_fewer_than_two_entries_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel"])
        assert any("two" in e.lower() or "entries" in e.lower() for e in errors)

    def test_missing_date_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("date" in e.lower() for e in errors)


class TestWriteVoucher:
    @pytest.mark.asyncio
    async def test_successful_write(self):
        mock_client = AsyncMock()
        mock_client.post_xml.return_value = """<RESPONSE>
<CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
<LASTVCHID>12345</LASTVCHID><LASTMID>0</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
</RESPONSE>"""
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_payment_voucher(
            date="20260404",
            debit_ledger="Travel Expenses",
            credit_ledger="Cash",
            amount=500.00,
            narration="Test",
        )
        assert result["success"] is True
        assert result["created"] == 1
        mock_client.post_xml.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_with_validation_error(self):
        mock_client = AsyncMock()
        writer = TallyWriter(client=mock_client, company="Test Co")
        # Unknown ledger should fail validation before calling Tally
        with pytest.raises(ValidationError, match="not found"):
            await writer.create_payment_voucher(
                date="20260404",
                debit_ledger="Nonexistent",
                credit_ledger="Cash",
                amount=500.00,
                narration="Test",
                known_ledgers=["Cash"],
            )
        mock_client.post_xml.assert_not_called()
