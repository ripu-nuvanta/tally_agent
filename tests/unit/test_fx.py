"""Tests for FX rate parsing, resolution, and chat override parsing."""
from decimal import Decimal

import pytest

from backend.services.fx import (
    parse_default_rates,
    resolve_fx_rate,
    parse_rate_override,
    recompute_entry_with_rate,
    classify_pending_message,
)


class TestParseDefaultRates:
    def test_basic(self):
        assert parse_default_rates("USD:83.5,EUR:90") == {"USD": 83.5, "EUR": 90.0}

    def test_empty_string(self):
        assert parse_default_rates("") == {}

    def test_lowercase_currency_uppercased(self):
        assert parse_default_rates("usd:83.5") == {"USD": 83.5}

    def test_whitespace_tolerated(self):
        assert parse_default_rates(" USD : 83.5 , EUR : 90 ") == {"USD": 83.5, "EUR": 90.0}

    def test_malformed_pairs_ignored(self):
        # "GBP" has no rate, "JPY:abc" has a non-numeric rate, "100" has no colon
        result = parse_default_rates("USD:83.5,GBP,JPY:abc,100,EUR:90")
        assert result == {"USD": 83.5, "EUR": 90.0}

    def test_all_malformed(self):
        assert parse_default_rates("garbage,no:colons:here:bad") == {}


class TestResolveFxRate:
    DEFAULTS = {"USD": 83.5, "EUR": 90.0}

    def test_inr_always_one(self):
        rate, source = resolve_fx_rate(
            "INR", None, None, default_rates=self.DEFAULTS, fallback=0.0
        )
        assert rate == Decimal("1")
        assert source == "inr"

    def test_inr_case_insensitive(self):
        rate, source = resolve_fx_rate(
            "inr", Decimal("83"), Decimal("90"), default_rates=self.DEFAULTS, fallback=75.0
        )
        # INR wins over everything
        assert rate == Decimal("1")
        assert source == "inr"

    def test_override_wins(self):
        rate, source = resolve_fx_rate(
            "USD", Decimal("83.5"), Decimal("84.5"),
            default_rates=self.DEFAULTS, fallback=75.0,
        )
        assert rate == Decimal("84.5")
        assert source == "override"

    def test_document_when_no_override(self):
        rate, source = resolve_fx_rate(
            "USD", Decimal("82.3"), None,
            default_rates=self.DEFAULTS, fallback=75.0,
        )
        assert rate == Decimal("82.3")
        assert source == "document"

    def test_per_currency_default_when_no_override_no_doc(self):
        rate, source = resolve_fx_rate(
            "USD", None, None,
            default_rates=self.DEFAULTS, fallback=75.0,
        )
        assert rate == Decimal("83.5")
        assert source == "default"

    def test_global_fallback_when_no_currency_default(self):
        rate, source = resolve_fx_rate(
            "GBP", None, None,
            default_rates=self.DEFAULTS, fallback=75.0,
        )
        assert rate == Decimal("75.0")
        assert source == "fallback"

    def test_unknown_currency_no_rate_returns_none(self):
        rate, source = resolve_fx_rate(
            "GBP", None, None,
            default_rates=self.DEFAULTS, fallback=0.0,
        )
        assert rate == Decimal("0")
        assert source == "none"

    def test_currency_lookup_is_case_insensitive(self):
        rate, source = resolve_fx_rate(
            "usd", None, None,
            default_rates=self.DEFAULTS, fallback=0.0,
        )
        assert rate == Decimal("83.5")
        assert source == "default"


class TestParseRateOverride:
    @pytest.mark.parametrize("message,expected", [
        ("use rate 84.5", 84.5),
        ("convert at 84.5", 84.5),
        ("rate = 84.5", 84.5),
        ("rate: 84.5", 84.5),
        ("@ 84.5", 84.5),
        ("84.50 per usd", 84.5),
        ("exchange rate 84", 84.0),
        ("Use Rate 84.5", 84.5),  # case-insensitive
        ("please use rate 83.25 thanks", 83.25),
    ])
    def test_accepted_phrasings(self, message, expected):
        assert parse_rate_override(message) == expected

    @pytest.mark.parametrize("message", [
        "rate of return",
        "the interest rate is high",
        "what is the exchange rate",
        "convert this for me",
        "hello there",
        "show me the trial balance",
        "",
    ])
    def test_rejected_no_number(self, message):
        assert parse_rate_override(message) is None

    @pytest.mark.parametrize("message", [
        "flat at 84.5 per day",  # "per day" is not a currency; bare "at" must not match
        "let's meet at 5",
        "at 3 pm",
        "the rent is fixed at 12000",
    ])
    def test_bare_at_number_is_not_a_rate(self, message):
        """Finding 3: a number after plain 'at' (no rate/currency cue) is NOT a rate."""
        assert parse_rate_override(message) is None

    def test_picks_number_adjacent_to_keyword(self):
        # "5 items" is noise; the rate keyword sits next to 84.5
        assert parse_rate_override("I have 5 items, use rate 84.5") == 84.5

    def test_at_symbol_with_rupee(self):
        assert parse_rate_override("@ 83.50") == 83.5


class TestRecomputeEntryWithRate:
    def _base_entry(self, **overrides):
        entry = {
            "id": "e1",
            "voucher_type": "Payment",
            "date": "20260404",
            "vendor_name": "Acme Inc",
            "amount": 0.0,
            "debit_ledger": "Travel Expenses",
            "credit_ledger": "Cash",
            "narration": "Acme Inc — Consulting",
            "gst_entries": [],
            "status": "draft",
            "warnings": [],
            "is_new_ledger": False,
            "suggested_parent": None,
            "original_currency": "USD",
            "original_amount": 100.0,
            "fx_rate": 0.0,
            "original_gst_entries": [],
        }
        entry.update(overrides)
        return entry

    def test_recompute_from_blocked_state(self):
        # prior fx_rate 0, amount 0 (no-rate blocked) -> recompute from original
        entry = self._base_entry(
            warnings=["No conversion rate for USD — reply 'use rate <n>' to set it (entry can't be written yet)."],
        )
        out = recompute_entry_with_rate(entry, 90.0)
        assert out["amount"] == 1000.0 * 9.0  # 100 * 90 = 9000
        assert out["amount"] == 9000.0
        assert out["fx_rate"] == 90.0
        assert out["status"] == "draft"
        # warning cleared
        assert out["warnings"] == []

    def test_recompute_scales_gst_legs(self):
        entry = self._base_entry(
            original_gst_entries=[
                {"ledger": "INPUT CGST", "amount": 9.0},
                {"ledger": "INPUT SGST", "amount": 9.0},
            ],
            gst_entries=[
                {"ledger": "INPUT CGST", "amount": 0.0},
                {"ledger": "INPUT SGST", "amount": 0.0},
            ],
        )
        out = recompute_entry_with_rate(entry, 90.0)
        assert out["gst_entries"] == [
            {"ledger": "INPUT CGST", "amount": 810.0},
            {"ledger": "INPUT SGST", "amount": 810.0},
        ]

    def test_narration_fx_trail_replaced(self):
        entry = self._base_entry(
            narration="Acme Inc — Consulting | FX: USD 100.00 @ ₹83.50 = ₹8,350.00",
            amount=8350.0,
            fx_rate=83.5,
        )
        out = recompute_entry_with_rate(entry, 90.0)
        # old trail stripped, new one appended once
        assert out["narration"].count("| FX:") == 1
        assert out["narration"] == "Acme Inc — Consulting | FX: USD 100.00 @ ₹90.00 = ₹9,000.00"

    def test_narration_fx_trail_added_when_absent(self):
        entry = self._base_entry(narration="Acme Inc — Consulting")
        out = recompute_entry_with_rate(entry, 90.0)
        assert out["narration"] == "Acme Inc — Consulting | FX: USD 100.00 @ ₹90.00 = ₹9,000.00"

    def test_clears_default_rate_warning(self):
        entry = self._base_entry(
            warnings=[
                "Used default USD→INR rate 83.5 — verify or reply 'use rate <n>'.",
                "Amount looks unusual.",
            ],
        )
        out = recompute_entry_with_rate(entry, 90.0)
        assert out["warnings"] == ["Amount looks unusual."]

    def test_clears_validate_extracted_amounts_fx_warning(self):
        # Group B Task 2 regression: validate_extracted_amounts emits a
        # "Foreign currency (<CUR>) with no exchange rate — please verify INR
        # amount" warning on the blocked entry. Setting an explicit rate makes it
        # stale, so recompute must drop it too — not only the orchestrator's
        # "No conversion rate ..." warning. Unrelated warnings stay.
        entry = self._base_entry(
            warnings=[
                "Foreign currency (USD) with no exchange rate — please verify INR amount",
                "No conversion rate for USD — reply 'use rate <n>' to set it (entry can't be written yet).",
                "Line items (90) + GST (18) = 108, but document total is 100 — please verify",
            ],
        )
        out = recompute_entry_with_rate(entry, 90.0)
        assert out["warnings"] == [
            "Line items (90) + GST (18) = 108, but document total is 100 — please verify"
        ]

    def test_half_up_rounding(self):
        entry = self._base_entry(original_amount=100.005)
        out = recompute_entry_with_rate(entry, 1.0)
        assert out["amount"] == 100.01

    def test_does_not_mutate_input(self):
        entry = self._base_entry()
        recompute_entry_with_rate(entry, 90.0)
        assert entry["amount"] == 0.0
        assert entry["fx_rate"] == 0.0

    def test_missing_original_amount_raises_not_silent_zero(self):
        """Finding 2: a non-INR entry with no original_amount must not silently
        produce ₹0 — it raises FxRecomputeError so the caller can clarify."""
        from backend.services.fx import FxRecomputeError
        entry = self._base_entry()
        del entry["original_amount"]
        with pytest.raises(FxRecomputeError):
            recompute_entry_with_rate(entry, 90.0)

    def test_zero_original_amount_raises_not_silent_zero(self):
        from backend.services.fx import FxRecomputeError
        entry = self._base_entry(original_amount=0.0)
        with pytest.raises(FxRecomputeError):
            recompute_entry_with_rate(entry, 90.0)

    def test_malformed_gst_leg_does_not_crash(self):
        """Finding 2: a gst leg missing 'ledger'/'amount' is skipped, not a KeyError."""
        entry = self._base_entry(
            original_gst_entries=[
                {"ledger": "INPUT CGST", "amount": 9.0},
                {"amount": 9.0},          # missing ledger
                {"ledger": "INPUT IGST"},  # missing amount
            ],
        )
        out = recompute_entry_with_rate(entry, 90.0)
        # only the well-formed leg survives
        assert out["gst_entries"] == [{"ledger": "INPUT CGST", "amount": 810.0}]


class TestClassifyPendingMessage:
    ENTRY = {"id": "e1", "original_currency": "USD", "original_amount": 100.0}

    def test_no_pending_entry_is_passthrough(self):
        assert classify_pending_message(None, "use rate 90") == ("passthrough", None)

    def test_override_with_number(self):
        assert classify_pending_message(self.ENTRY, "use rate 90") == ("override", 90.0)

    def test_rate_words_without_number_is_clarify(self):
        assert classify_pending_message(self.ENTRY, "what rate should I use?") == ("clarify", None)

    def test_unrelated_message_is_passthrough(self):
        assert classify_pending_message(self.ENTRY, "show me the trial balance") == ("passthrough", None)

    def test_convert_keyword_without_number_is_clarify(self):
        assert classify_pending_message(self.ENTRY, "please convert this") == ("clarify", None)


class TestSharedHelpers:
    """Finding 4: rounding + FX-trail are single implementations shared across paths."""

    def test_fx_round_inr_is_voucher_builder_impl(self):
        # fx.py must reuse voucher_builder's Decimal rounding, not keep its own copy.
        from backend.services import fx as fx_mod
        from backend.services import voucher_builder as vb_mod
        assert fx_mod._round_inr_dec is vb_mod._round_inr

    def test_fx_trail_is_voucher_builder_impl(self):
        from backend.services import fx as fx_mod
        from backend.services import voucher_builder as vb_mod
        assert fx_mod._fx_trail is vb_mod._fx_trail


class TestOverrideBuilderParity:
    """Finding 4: the override path and the builder path must produce the SAME
    INR amount and the SAME FX trail for identical inputs (anti-drift guard)."""

    def test_same_inr_amount_and_trail(self):
        from decimal import Decimal
        from backend.services.document_parser import ExtractedDocument
        from backend.services.voucher_builder import build_payment_voucher_data

        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Acme Inc",
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            original_currency="USD",
        )
        # Builder path with a doc/override rate of 90.
        vd = build_payment_voucher_data(
            doc, "Consulting", "Cash", override=Decimal("90"),
            default_rates={}, fallback=0.0,
        )
        # Override path on an equivalent pending entry, same rate.
        entry = {
            "id": "p1",
            "narration": "Acme Inc",
            "amount": 0.0,
            "fx_rate": 0.0,
            "gst_entries": [],
            "original_gst_entries": [],
            "original_currency": "USD",
            "original_amount": 100.0,
            "warnings": [],
            "status": "draft",
        }
        out = recompute_entry_with_rate(entry, 90.0)

        assert out["amount"] == float(vd.amount)
        # FX trail substring identical across both paths
        trail = " | FX: USD 100.00 @ ₹90.00 = ₹9,000.00"
        assert vd.narration.endswith(trail)
        assert out["narration"].endswith(trail)
