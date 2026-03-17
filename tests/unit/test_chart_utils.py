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


from backend.agents.utils import parse_markdown_table_for_chart


class TestParseMarkdownTableForChart:
    """Tests for parse_markdown_table_for_chart()."""

    def test_single_table(self):
        text = """Some intro text.

| Month | Sales |
|-------|-------|
| Jan | ₹1,00,000 |
| Feb | ₹2,00,000 |
| Mar | ₹3,00,000 |

Some outro text."""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Month", "Sales"]
        assert len(result["rows"]) == 3
        assert result["rows"][0] == ["Jan", 100000.0]

    def test_no_table(self):
        text = "No tables here, just text."
        assert parse_markdown_table_for_chart(text) is None

    def test_table_too_small(self):
        text = """| Name | Value |
|------|-------|
| Only | 100 |"""
        assert parse_markdown_table_for_chart(text) is None

    def test_multiple_tables_picks_most_rows(self):
        text = """Summary:
| Category | Total |
|----------|-------|
| A | 100 |
| B | 200 |

Details:
| Month | Amount | Growth |
|-------|--------|--------|
| Jan | 50 | 5% |
| Feb | 60 | 10% |
| Mar | 70 | 15% |
| Apr | 80 | 20% |
"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Month", "Amount", "Growth"]
        assert len(result["rows"]) == 4

    def test_multiple_tables_same_rows_picks_later(self):
        text = """First:
| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |

Second:
| X | Y |
|---|---|
| 5 | 6 |
| 7 | 8 |
"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["X", "Y"]

    def test_rank_column_skipped(self):
        text = """| Rank | Customer | Sales |
|------|----------|-------|
| 1 | Alice | 100 |
| 2 | Bob | 200 |
| 3 | Carol | 300 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Customer", "Sales"]
        assert result["rows"][0][0] == "Alice"

    def test_hash_column_skipped(self):
        text = """| # | Ledger | Amount |
|---|--------|--------|
| 1 | Rent | 50000 |
| 2 | Salary | 100000 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Ledger", "Amount"]

    def test_emoji_rank_column_skipped(self):
        text = """| # | Expense | Amount |
|---|---------|--------|
| 🥇 | Salaries | 1000000 |
| 🥈 | Rent | 300000 |
| 🥉 | Travel | 15000 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Expense", "Amount"]
        assert result["rows"][0][0] == "Salaries"

    def test_sequential_int_column_skipped(self):
        text = """| No | Item | Price |
|----|------|-------|
| 1 | Apple | 10 |
| 2 | Banana | 20 |
| 3 | Cherry | 30 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Item", "Price"]

    def test_numeric_conversion_with_emoji(self):
        text = """| Month | Sales | Change % |
|-------|-------|----------|
| Oct | ₹5,44,000 | — (base) |
| Nov | ₹2,29,500 | 🔴 −57.8% |
| Dec | ₹4,17,750 | 🟢 +82.0% |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["rows"][1][2] == -57.8
        assert result["rows"][2][2] == 82.0

    def test_total_row_preserved_in_parser(self):
        text = """| Customer | Sales |
|----------|-------|
| Alice | 100 |
| Bob | 200 |
| Total | 300 |"""
        result = parse_markdown_table_for_chart(text)
        assert len(result["rows"]) == 3

    def test_text_values_kept_as_strings(self):
        text = """| Month | Sales | Status |
|-------|-------|--------|
| Jan | 100 | Good |
| Feb | 200 | Bad |"""
        result = parse_markdown_table_for_chart(text)
        assert result["rows"][0][2] == "Good"
        assert result["rows"][1][2] == "Bad"


from backend.agents.utils import parse_all_markdown_tables


class TestParseAllMarkdownTables:
    def test_returns_all_tables(self):
        text = """Table 1:
| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |

Table 2:
| X | Y | Z |
|---|---|---|
| a | 5 | 6 |
| b | 7 | 8 |
| c | 9 | 10 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 2
        assert tables[0]["headers"] == ["A", "B"]
        assert tables[1]["headers"] == ["X", "Y", "Z"]

    def test_skips_small_tables(self):
        text = """| A | B |
|---|---|
| 1 | 2 |

| X | Y |
|---|---|
| a | 3 |
| b | 4 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 1  # First table has only 1 row, skipped

    def test_empty_text(self):
        assert parse_all_markdown_tables("no tables here") == []

    def test_ordinal_columns_stripped(self):
        text = """| Rank | Customer | Sales |
|------|----------|-------|
| 1 | Alice | 100 |
| 2 | Bob | 200 |
| 3 | Carol | 300 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 1
        assert tables[0]["headers"] == ["Customer", "Sales"]

    def test_mostly_text_column_not_treated_as_ordinal(self):
        """A column where most values are text (parse to 0.0) should NOT be ordinal-detected."""
        text = """| Status | Customer | Sales |
|--------|----------|-------|
| Active | Alice | 100 |
| Inactive | Bob | 200 |
| Active | Carol | 300 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 1
        # "Status" column has mostly text values — must NOT be stripped as ordinal
        assert "Status" in tables[0]["headers"]
        assert tables[0]["headers"][0] == "Status"

    def test_numeric_conversion(self):
        text = """| Month | Sales |
|-------|-------|
| Jan | ₹1,00,000 |
| Feb | ₹2,00,000 |
| Mar | ₹3,00,000 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 1
        assert tables[0]["rows"][0] == ["Jan", 100000.0]

    def test_returns_all_tables_preserves_order(self):
        text = """First table:
| Month | Revenue |
|-------|---------|
| Jan | 100 |
| Feb | 200 |

Second table:
| Quarter | Profit |
|---------|--------|
| Q1 | 50 |
| Q2 | 75 |
| Q3 | 80 |
"""
        tables = parse_all_markdown_tables(text)
        assert len(tables) == 2
        assert tables[0]["headers"] == ["Month", "Revenue"]
        assert tables[1]["headers"] == ["Quarter", "Profit"]
        assert len(tables[0]["rows"]) == 2
        assert len(tables[1]["rows"]) == 3
