"""Tests for 3-tier ledger mapping: stored rules → fuzzy → AI."""
import pytest
from unittest.mock import AsyncMock

from backend.services.ledger_mapper import LedgerMapper, MappingResult


class TestStoredRuleMapping:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = [
            {"vendor_pattern": "uber", "ledger_name": "Travel Expenses",
             "voucher_type": "Payment", "confidence": 1.0, "use_count": 5},
        ]
        result = await mapper.find_mapping("Uber", "Payment", tally_ledgers=[])
        assert result.ledger_name == "Travel Expenses"
        assert result.source == "stored_rule"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_no_stored_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        result = await mapper.find_mapping("Unknown Vendor", "Payment", tally_ledgers=["Cash"])
        assert result.source != "stored_rule"

    @pytest.mark.asyncio
    async def test_voucher_type_mismatch_skips_stored(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = [
            {"vendor_pattern": "uber", "ledger_name": "Travel Expenses",
             "voucher_type": "Sales", "confidence": 1.0, "use_count": 5},
        ]
        # Same vendor, different voucher type — should NOT match
        result = await mapper.find_mapping("Uber", "Payment", tally_ledgers=["Cash"])
        assert result.source != "stored_rule"


class TestFuzzyMapping:
    @pytest.mark.asyncio
    async def test_fuzzy_ledger_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        result = await mapper.find_mapping(
            "Reliance Jio Infocomm Ltd",
            "Payment",
            tally_ledgers=["Reliance Jio", "Cash", "Bank Account"],
        )
        assert result.ledger_name == "Reliance Jio"
        assert result.source == "fuzzy_match"

    @pytest.mark.asyncio
    async def test_no_fuzzy_match_falls_through(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        mapper._ai_suggest = AsyncMock(return_value=MappingResult(
            ledger_name="Office Supplies",
            source="ai_suggestion",
            confidence=0.7,
        ))
        result = await mapper.find_mapping(
            "Random Shop XYZ",
            "Payment",
            tally_ledgers=["Cash", "Bank Account"],
        )
        assert result.source == "ai_suggestion"

    @pytest.mark.asyncio
    async def test_default_ai_suggest_returns_new_ledger(self):
        """Default _ai_suggest implementation returns a 'create new ledger' result."""
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        result = await mapper.find_mapping(
            "Random Shop XYZ",
            "Payment",
            tally_ledgers=["Cash"],
        )
        assert result.source == "ai_suggestion"
        assert result.is_new_ledger is True
        assert result.suggested_parent is not None


class TestLearning:
    def test_store_user_correction(self):
        mapper = LedgerMapper()
        mapper.learn_mapping(
            vendor="Swiggy",
            ledger_name="Staff Welfare",
            voucher_type="Payment",
            source="user_correction",
        )
        assert len(mapper._stored_mappings) == 1
        assert mapper._stored_mappings[0]["vendor_pattern"] == "swiggy"
        assert mapper._stored_mappings[0]["confidence"] == 1.0

    def test_correction_overrides_existing(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = [
            {"vendor_pattern": "swiggy", "ledger_name": "Food Expenses",
             "voucher_type": "Payment", "confidence": 0.8, "use_count": 3,
             "created_from": "ai_suggestion"},
        ]
        mapper.learn_mapping(
            vendor="Swiggy",
            ledger_name="Staff Welfare",
            voucher_type="Payment",
            source="user_correction",
        )
        assert len(mapper._stored_mappings) == 1
        assert mapper._stored_mappings[0]["ledger_name"] == "Staff Welfare"
        assert mapper._stored_mappings[0]["confidence"] == 1.0

    def test_ai_suggestion_default_confidence(self):
        mapper = LedgerMapper()
        mapper.learn_mapping(
            vendor="Zomato",
            ledger_name="Food Expenses",
            voucher_type="Payment",
            source="ai_suggestion",
        )
        assert mapper._stored_mappings[0]["confidence"] == 0.8
