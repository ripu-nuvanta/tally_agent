"""Tests for shared chart utility functions in backend.agents.utils."""

import pytest
from backend.agents.utils import to_numeric


class TestToNumeric:
    """Enhanced _to_numeric with emoji/symbol stripping."""

    def test_int(self):
        assert to_numeric(42) == 42.0

    def test_float(self):
        assert to_numeric(3.14) == 3.14

    def test_plain_string(self):
        assert to_numeric("123") == 123.0

    def test_negative(self):
        assert to_numeric("-45.6") == -45.6

    def test_currency_inr(self):
        assert to_numeric("₹7,08,500.00") == 708500.0

    def test_percentage(self):
        assert to_numeric("34.4%") == 34.4

    def test_bold_markers(self):
        assert to_numeric("**₹5,44,000**") == 544000.0

    def test_emoji_negative_percent(self):
        assert to_numeric("🔴 −57.8%") == -57.8

    def test_emoji_positive_percent(self):
        assert to_numeric("🟢 +82.0%") == 82.0

    def test_arrow_down_currency(self):
        assert to_numeric("▼ −₹3,14,500.00") == -314500.0

    def test_arrow_up_currency(self):
        assert to_numeric("▲ +₹1,88,250.00") == 188250.0

    def test_checkmark_emoji(self):
        assert to_numeric("✅ Above") == 0.0

    def test_down_arrow_emoji(self):
        assert to_numeric("⬇️ Below") == 0.0

    def test_medal_emoji_rank(self):
        assert to_numeric("🥇 1") == 1.0

    def test_medal_emoji_rank_2(self):
        assert to_numeric("🥈 2") == 2.0

    def test_dash_base(self):
        assert to_numeric("— (base)") == 0.0

    def test_single_dash(self):
        assert to_numeric("—") == 0.0

    def test_na(self):
        assert to_numeric("N/A") == 0.0

    def test_pure_text(self):
        assert to_numeric("Global IT Solutions") == 0.0

    def test_unicode_minus(self):
        assert to_numeric("−100.0%") == -100.0

    def test_none(self):
        assert to_numeric(None) == 0.0

    def test_flat_arrow(self):
        assert to_numeric("➡️ Flat") == 0.0

    def test_parenthetical_note(self):
        assert to_numeric("(Q3 lump-sum; Q4 bill pending)") == 0.0

    def test_new_in_q4(self):
        assert to_numeric("New in Q4") == 0.0

    def test_negative_percentage_points(self):
        assert to_numeric("−23.0 pp") == -23.0
