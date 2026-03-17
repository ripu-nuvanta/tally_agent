"""Unit tests for ChartAgent — rule-based chart type selection and data formatting.

Pure Python, no mocking needed — all tests are deterministic.
"""

import pytest

from backend.agents.chart_agent import (
    ChartAgent,
    _to_numeric,
    _select_chart_type,
    _generate_title,
    _format_xy_data,
    _format_pie_data,
    _build_config,
    _EXCLUDED_CHART_COLUMNS,
    _is_secondary_axis_column,
    _is_excluded_column,
    _trim_trailing_zeros,
    _detect_scale_mismatches,
)


# ---------------------------------------------------------------------------
# Tests: Chart type selection
# ---------------------------------------------------------------------------


class TestSelectChartType:
    def test_too_few_rows_returns_table_only(self):
        assert _select_chart_type("bar", "top_n", [[1]]) == "table_only"

    def test_comparison_returns_grouped_bar(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("", "comparison", rows) == "grouped_bar"

    def test_trend_with_enough_points_returns_line(self):
        rows = [[1], [2], [3], [4]]
        assert _select_chart_type("", "trend", rows) == "line"

    def test_trend_few_points_returns_grouped_bar(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("", "trend", rows) == "grouped_bar"

    def test_top_n_returns_bar(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("", "top_n", rows) == "bar"

    def test_aggregation_few_items_returns_pie(self):
        rows = [[1], [2], [3], [4]]
        assert _select_chart_type("", "aggregation", rows) == "pie"

    def test_aggregation_many_items_returns_bar(self):
        rows = [[i] for i in range(10)]
        assert _select_chart_type("", "aggregation", rows) == "bar"

    def test_suggestion_overrides_query_type(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("line", "top_n", rows) == "line"

    def test_pie_suggestion_with_many_rows_still_uses_pie(self):
        rows = [[i] for i in range(10)]
        assert _select_chart_type("pie", "aggregation", rows) == "pie"

    def test_table_only_suggestion_is_honored(self):
        """table_only suggestion should return table_only, not defer to query_type."""
        rows = [[1], [2], [3]]
        assert _select_chart_type("table_only", "comparison", rows) == "table_only"
        assert _select_chart_type("table_only", "top_n", rows) == "table_only"
        assert _select_chart_type("table_only", "aggregation", rows) == "table_only"


# ---------------------------------------------------------------------------
# Tests: ChartAgent.execute
# ---------------------------------------------------------------------------


class TestChartAgentExecute:
    def setup_method(self):
        self.agent = ChartAgent()

    def test_returns_none_when_not_required(self):
        result = self.agent.execute(
            {"data": {"headers": ["A"], "rows": [[1]]}},
            "simple_lookup",
            requires_chart=False,
        )
        assert result is None

    def test_returns_none_for_empty_data(self):
        result = self.agent.execute(
            {"data": {"headers": [], "rows": []}},
            "top_n",
            requires_chart=True,
        )
        assert result is None

    def test_returns_none_for_single_row(self):
        result = self.agent.execute(
            {"data": {"headers": ["Name", "Amount"], "rows": [["A", 100]]}},
            "top_n",
            requires_chart=True,
        )
        assert result is None

    def test_bar_chart_for_top_n(self):
        data = {
            "data": {
                "headers": ["Customer", "Sales"],
                "rows": [
                    ["Alpha", 5000],
                    ["Beta", 3000],
                    ["Gamma", 2000],
                ],
            },
        }
        result = self.agent.execute(data, "top_n", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "bar"
        assert len(result["data"]) == 3
        assert result["data"][0]["label"] == "Alpha"
        assert result["data"][0]["Sales"] == 5000.0

    def test_composed_chart_for_comparison_with_change_pct(self):
        data = {
            "data": {
                "headers": ["Item", "Q1", "Q2", "Change", "Change %"],
                "rows": [
                    ["Sales", 10000, 12000, 2000, "+20.0%"],
                    ["Expenses", 5000, 5500, 500, "+10.0%"],
                    ["Profit", 5000, 6500, 1500, "+30.0%"],
                ],
            },
        }
        result = self.agent.execute(data, "comparison", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "composed"
        assert result["data"][0]["Q1"] == 10000.0
        assert result["data"][0]["Q2"] == 12000.0
        # "Change" excluded, "Change %" kept for secondary axis
        assert "Change" not in result["data"][0]
        assert "Change %" in result["data"][0]
        assert result["config"]["secondary_y_keys"] == ["Change %"]
        assert result["config"]["secondary_colors"] == ["#9CA3AF"]

    def test_composed_chart_for_trend_with_change_pct(self):
        data = {
            "data": {
                "headers": ["Period", "Revenue", "Change", "Change %"],
                "rows": [
                    ["Jan", 1000, "—", "—"],
                    ["Feb", 1200, "+200.00", "+20.0%"],
                    ["Mar", 1100, "-100.00", "-8.3%"],
                    ["Apr", 1400, "+300.00", "+27.3%"],
                ],
            },
        }
        result = self.agent.execute(data, "trend", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "composed"
        assert len(result["data"]) == 4

    def test_no_composed_override_without_change_pct(self):
        """Without Change % header, chart_type stays as original."""
        data = {
            "data": {
                "headers": ["Customer", "Sales"],
                "rows": [["A", 5000], ["B", 3000], ["C", 2000]],
            },
        }
        result = self.agent.execute(data, "top_n", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "bar"
        assert "secondary_y_keys" not in result["config"]

    def test_pie_chart_for_aggregation(self):
        data = {
            "chart_suggestion": "pie",
            "data": {
                "headers": ["Category", "Amount"],
                "rows": [
                    ["Sales", 50000],
                    ["Services", 30000],
                    ["Other", 20000],
                ],
            },
        }
        result = self.agent.execute(data, "aggregation", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "pie"
        assert len(result["data"]) == 3
        assert result["data"][0]["value"] == 50000.0

    def test_pie_chart_groups_beyond_7_slices(self):
        rows = [[f"Item {i}", i * 100] for i in range(10, 0, -1)]
        data = {
            "chart_suggestion": "pie",
            "data": {"headers": ["Item", "Amount"], "rows": rows},
        }
        result = self.agent.execute(data, "aggregation", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "pie"
        assert len(result["data"]) == 7  # 6 items + Others
        assert result["data"][-1]["label"] == "Others"

    def test_config_has_required_keys(self):
        data = {
            "data": {
                "headers": ["Name", "Amount"],
                "rows": [["A", 100], ["B", 200], ["C", 300]],
            },
        }
        result = self.agent.execute(data, "top_n", requires_chart=True)
        assert result is not None
        config = result["config"]
        assert "x_key" in config
        assert "y_keys" in config
        assert "colors" in config
        assert config["x_key"] == "label"

    def test_chart_with_analysis_result_shape(self):
        """Analysis agent output shape works as input."""
        data = {
            "message": "Top customers...",
            "data": {
                "headers": ["Customer", "Sales"],
                "rows": [["A", 500], ["B", 300], ["C", 200]],
            },
            "insights": ["A is the top customer"],
            "chart_suggestion": "bar",
        }
        result = self.agent.execute(data, "top_n", requires_chart=True)
        assert result is not None
        assert result["chart_type"] == "bar"


# ---------------------------------------------------------------------------
# Tests: _to_numeric helper
# ---------------------------------------------------------------------------


class TestToNumeric:
    def test_int(self):
        assert _to_numeric(100) == 100.0

    def test_float(self):
        assert _to_numeric(3.14) == 3.14

    def test_string_number(self):
        assert _to_numeric("1234.56") == 1234.56

    def test_indian_formatted_string(self):
        assert _to_numeric("₹12,34,567.00") == 1234567.0

    def test_non_numeric_string(self):
        assert _to_numeric("hello") == 0.0

    def test_none(self):
        assert _to_numeric(None) == 0.0

    def test_percentage_string(self):
        assert _to_numeric("+1.7%") == 1.7

    def test_negative_percentage(self):
        assert _to_numeric("-13.0%") == -13.0

    def test_dash(self):
        """First row of trend data uses '—' for no-prior-period."""
        assert _to_numeric("—") == 0.0

    def test_na(self):
        assert _to_numeric("N/A") == 0.0

    def test_na_base_zero(self):
        assert _to_numeric("N/A (base is zero)") == 0.0

    def test_positive_with_plus(self):
        assert _to_numeric("+100.0%") == 100.0


# ---------------------------------------------------------------------------
# Tests: _format_xy_data — excluded columns
# ---------------------------------------------------------------------------


class TestFormatXyDataExclusions:
    def test_change_column_excluded_from_data_points(self):
        headers = ["Period", "Revenue", "Change", "Change %"]
        rows = [["Jan", 1000, 200, "+20%"], ["Feb", 1200, -100, "-8%"]]
        result = _format_xy_data(headers, rows)
        assert "Change" not in result[0]
        assert "Revenue" in result[0]
        assert "Change %" in result[0]

    def test_no_excluded_columns_all_present(self):
        headers = ["Name", "Sales", "Profit"]
        rows = [["A", 100, 50], ["B", 200, 80]]
        result = _format_xy_data(headers, rows)
        assert result[0] == {"label": "A", "Sales": 100.0, "Profit": 50.0}


# ---------------------------------------------------------------------------
# Tests: _generate_title — better titles
# ---------------------------------------------------------------------------


class TestGenerateTitle:
    def test_title_uses_first_value_header_not_last(self):
        headers = ["Period", "Revenue", "Change", "Change %"]
        title = _generate_title("trend", headers)
        assert title == "Trend Analysis: Revenue by Period"

    def test_title_with_only_value_columns(self):
        headers = ["Customer", "Sales"]
        title = _generate_title("top_n", headers)
        assert title == "Ranking: Sales by Customer"

    def test_title_fallback_when_all_excluded(self):
        """Edge case: only excluded headers after first."""
        headers = ["Period", "Change"]
        title = _generate_title("trend", headers)
        # Falls back to headers[1] since no non-excluded headers
        assert title == "Trend Analysis: Change by Period"

    def test_title_single_header(self):
        headers = ["Name"]
        title = _generate_title("simple_lookup", headers)
        assert title == "Data Overview"


# ---------------------------------------------------------------------------
# Tests: _build_config — secondary axis
# ---------------------------------------------------------------------------


class TestBuildConfigSecondaryAxis:
    def test_secondary_keys_present_when_change_pct(self):
        config = _build_config("grouped_bar", ["Item", "Q1", "Q2", "Change", "Change %"])
        assert config["y_keys"] == ["Q1", "Q2"]
        assert config["secondary_y_keys"] == ["Change %"]
        assert config["secondary_colors"] == ["#9CA3AF"]
        assert config["show_legend"] is True

    def test_no_secondary_keys_without_change_pct(self):
        config = _build_config("bar", ["Name", "Amount"])
        assert config["y_keys"] == ["Amount"]
        assert "secondary_y_keys" not in config
        assert config["show_legend"] is False

    def test_pie_chart_clears_secondary_keys(self):
        config = _build_config("pie", ["Category", "Amount", "Change %"])
        assert config["y_keys"] == ["value"]
        assert "secondary_y_keys" not in config

    def test_show_legend_true_with_multiple_y_keys(self):
        config = _build_config("grouped_bar", ["Item", "Q1", "Q2"])
        assert config["show_legend"] is True

    def test_composed_suggestion_accepted(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("composed", "comparison", rows) == "composed"


# ---------------------------------------------------------------------------
# Tests: _trim_trailing_zeros
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests: _format_xy_data — Total/Grand Total row exclusion
# ---------------------------------------------------------------------------


def test_format_xy_data_excludes_total_row():
    """Total/Grand Total rows should be excluded from chart data."""
    from backend.agents.chart_agent import _format_xy_data
    headers = ["Customer", "Sales"]
    rows = [
        ["HCODE", 1642000],
        ["SMARTBIKE", 1062000],
        ["Total", 2704000],
    ]
    data = _format_xy_data(headers, rows)
    labels = [d["label"] for d in data]
    assert "Total" not in labels
    assert len(data) == 2

def test_format_xy_data_excludes_grand_total():
    from backend.agents.chart_agent import _format_xy_data
    headers = ["Ledger", "Q2", "Q3"]
    rows = [
        ["SALES HARYANA", 895000, 975000],
        ["SALES EXPORT", 0, 182500],
        ["Grand Total", 895000, 1157500],
    ]
    data = _format_xy_data(headers, rows)
    labels = [d["label"] for d in data]
    assert "Grand Total" not in labels
    assert len(data) == 2


def test_trim_trailing_zeros_removes_empty_tail():
    """With only 1 nonzero row (span < 3), Rule D preserves all rows for context."""
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Jan 2026", 611850, "+270650.00", "+30.7%"],
        ["Feb 2026", 0, "-611850.00", "-100.0%"],
        ["Mar 2026", 0, "+0.00", "N/A"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    # Span is 1 (only Jan 2026 nonzero), which is < 3 — Rule D preserves all rows
    assert len(trimmed) == 3
    assert trimmed[0][0] == "Jan 2026"

def test_trim_trailing_zeros_keeps_mid_zeros():
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Apr 2025", 0, "—", "—"],
        ["May 2025", 100, "+100.00", "N/A"],
        ["Jun 2025", 0, "-100.00", "-100.0%"],
        ["Jul 2025", 200, "+200.00", "N/A"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 3  # leading zero trimmed, mid-sequence zero preserved
    assert trimmed[0][0] == "May 2025"
    assert trimmed[1][0] == "Jun 2025"  # mid-zero kept
    assert trimmed[2][0] == "Jul 2025"

class TestNonNumericColumnFiltering:
    """ChartAgent should skip non-numeric columns (text, status) from y_keys."""

    def test_identify_numeric_columns_filters_text(self):
        from backend.agents.chart_agent import _identify_numeric_columns
        headers = ["Item", "Closing Stock", "Total Sold", "Days of Cover", "Status"]
        rows = [
            ["Samsung Monitor", 20, 23, 141.7, "Watch"],
            ["HP Laptop", 10, 10, 163.0, "OK"],
            ["Dell Desktop", 8, 8, 163.0, "OK"],
        ]
        numeric_cols = _identify_numeric_columns(headers, rows)
        assert "Item" not in numeric_cols
        assert "Status" not in numeric_cols
        assert "Closing Stock" in numeric_cols
        assert "Days of Cover" in numeric_cols

    def test_build_config_uses_only_numeric_y_keys(self):
        from backend.agents.chart_agent import _build_config
        headers = ["Rank", "Item", "Stock", "Days of Cover", "Status"]
        rows = [
            [1, "Monitor", 20, 141.7, "Watch"],
            [2, "Laptop", 10, 163.0, "OK"],
        ]
        config = _build_config("bar", headers, rows)
        assert "Item" not in config["y_keys"]
        assert "Status" not in config["y_keys"]
        assert "Stock" in config["y_keys"]
        assert "Days of Cover" in config["y_keys"]

    def test_chart_agent_returns_none_when_no_numeric_columns(self):
        from backend.agents.chart_agent import ChartAgent
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Name", "Category", "Status"],
                "rows": [["A", "Cat1", "OK"], ["B", "Cat2", "Watch"]],
            },
            "chart_suggestion": "bar",
        }
        result = agent.execute(data, "top_n", True)
        assert result is None

    def test_format_xy_data_excludes_non_numeric_columns(self):
        """_format_xy_data should only include columns in the provided numeric set."""
        from backend.agents.chart_agent import _format_xy_data
        headers = ["Item", "Stock", "Status", "Days"]
        rows = [
            ["Monitor", 20, "OK", 141.7],
            ["Laptop", 10, "Watch", 50.3],
        ]
        numeric_cols = {"Stock", "Days"}
        result = _format_xy_data(headers, rows, numeric_cols)
        assert result[0] == {"label": "Monitor", "Stock": 20.0, "Days": 141.7}
        assert "Status" not in result[0]
        assert result[1] == {"label": "Laptop", "Stock": 10.0, "Days": 50.3}

    def test_chart_agent_mixed_columns_charts_only_numeric(self):
        from backend.agents.chart_agent import ChartAgent
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Item", "Closing Stock", "Total Sold", "Avg Sales/Month", "Days of Cover", "Status"],
                "rows": [
                    ["Samsung Monitor", 20, 23, 4.2, 141.7, "Watch"],
                    ["HP Laptop", 10, 10, 1.8, 163.0, "OK"],
                    ["Dell Desktop", 8, 8, 1.5, 163.0, "OK"],
                ],
            },
            "chart_suggestion": "bar",
        }
        result = agent.execute(data, "top_n", True)
        assert result is not None
        assert "Item" not in result["config"]["y_keys"]
        assert "Status" not in result["config"]["y_keys"]
        assert "Days of Cover" in result["config"]["y_keys"]


# ---------------------------------------------------------------------------
# Tests: Secondary axis detection — pattern-based
# ---------------------------------------------------------------------------


class TestSecondaryAxisDetection:
    """Secondary axis should detect percentage columns beyond just 'Change %'."""

    def test_detects_percentage_columns_as_secondary(self):
        headers = ["Month", "Sales", "MoM %"]
        rows = [["Jan", 100000, 5.2], ["Feb", 110000, 10.0]]
        config = _build_config("line", headers, rows)
        assert "MoM %" in config.get("secondary_y_keys", [])
        assert "Sales" in config["y_keys"]
        assert "MoM %" not in config["y_keys"]

    def test_detects_vs_avg_percentage_as_secondary(self):
        headers = ["Month", "Amount", "% vs Avg"]
        rows = [["Jan", 100000, 15.3], ["Feb", 90000, -8.2]]
        config = _build_config("bar", headers, rows)
        assert "% vs Avg" in config.get("secondary_y_keys", [])
        assert "Amount" in config["y_keys"]

    def test_excludes_absolute_change_from_primary(self):
        headers = ["Month", "Revenue", "MoM Change", "MoM %"]
        rows = [["Jan", 500000, 0, 0], ["Feb", 550000, 50000, 10.0]]
        config = _build_config("line", headers, rows)
        assert "Revenue" in config["y_keys"]
        assert "MoM Change" not in config["y_keys"]
        assert "MoM %" in config.get("secondary_y_keys", [])

    def test_standard_change_pct_still_works(self):
        """Original 'Change %' header still detected as secondary."""
        headers = ["Period", "Revenue", "Change", "Change %"]
        rows = [["Jan", 1000, 200, 20.0], ["Feb", 1200, -100, -8.3]]
        config = _build_config("line", headers, rows)
        assert "Change %" in config.get("secondary_y_keys", [])
        assert "Change" not in config["y_keys"]
        assert "Revenue" in config["y_keys"]

    def test_format_xy_data_includes_secondary_axis_columns(self):
        """Secondary axis columns should be included in xy data even if not in numeric_cols."""
        headers = ["Month", "Sales", "MoM %"]
        rows = [["Jan", 100000, 5.2], ["Feb", 110000, 10.0]]
        numeric_cols = {"Sales"}  # MoM % not in numeric_cols
        result = _format_xy_data(headers, rows, numeric_cols)
        assert "MoM %" in result[0]
        assert result[0]["MoM %"] == 5.2

    def test_generate_title_excludes_secondary_columns(self):
        """Title should use primary value columns, not percentage columns."""
        headers = ["Period", "Revenue", "MoM %"]
        title = _generate_title("trend", headers)
        assert title == "Trend Analysis: Revenue by Period"


class TestTableOnlyOverride:
    """ChartAgent should force table_only for wide tables with text columns."""

    def test_force_table_only_when_many_non_numeric_columns(self):
        """Tables with 3+ non-numeric columns should be table_only."""
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Rank", "Item", "Group", "Stock", "Avg Sales", "Days", "Status"],
                "rows": [
                    [1, "Monitor", "Electronics", 20, 4.2, 141.7, "OK"],
                    [2, "Laptop", "Electronics", 10, 1.8, 50.3, "Watch"],
                    [3, "Desktop", "Electronics", 0, 1.3, 0, "Critical"],
                ],
            },
            "chart_suggestion": "bar",
        }
        result = agent.execute(data, "top_n", True)
        assert result is None  # table_only → None

    def test_allows_chart_when_few_non_numeric_columns(self):
        """Tables with 1-2 non-numeric columns (label + maybe one text) should chart."""
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Customer", "Sales Amount"],
                "rows": [
                    ["Apex", 500000],
                    ["Beta", 300000],
                    ["Gamma", 200000],
                ],
            },
            "chart_suggestion": "bar",
        }
        result = agent.execute(data, "top_n", True)
        assert result is not None
        assert result["chart_type"] == "bar"

    def test_allows_chart_with_two_text_columns(self):
        """Tables with exactly 2 non-numeric columns among non-label headers should still chart."""
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Item", "Category", "Status", "Sales Amount"],
                "rows": [
                    ["Monitor", "Electronics", "OK", 500000],
                    ["Laptop", "Electronics", "Watch", 300000],
                    ["Printer", "Office", "OK", 200000],
                ],
            },
            "chart_suggestion": "bar",
        }
        result = agent.execute(data, "top_n", True)
        assert result is not None  # 2 text cols — under threshold

    def test_excludes_secondary_axis_columns_from_non_numeric_count(self):
        """Percentage columns on secondary axis should NOT count toward non-numeric."""
        agent = ChartAgent()
        data = {
            "data": {
                "headers": ["Month", "Revenue", "MoM %"],
                "rows": [
                    ["Jan", 500000, 5.2],
                    ["Feb", 550000, 10.0],
                    ["Mar", 600000, 9.1],
                ],
            },
            "chart_suggestion": "line",
        }
        result = agent.execute(data, "trend", True)
        assert result is not None  # MoM % is secondary axis, not a text column


def test_format_pie_data_skips_text_columns():
    """Pie chart picks first numeric column, not hardcoded index 1."""
    from backend.agents.chart_agent import _format_pie_data
    headers = ["Expense Ledger", "Group", "Amount (₹)", "% of Total"]
    rows = [
        ["Purchase - Electronics", "Purchase Accounts", "₹23,22,100.00", "60.1%"],
        ["Salaries", "Indirect Expenses", "₹10,00,000.00", "25.9%"],
        ["Rent", "Indirect Expenses", "₹3,00,000.00", "7.8%"],
    ]
    data = _format_pie_data(headers, rows)
    assert data[0]["value"] > 0, f"Expected numeric value, got {data[0]['value']}"
    assert data[0]["value"] == 2322100.0  # Amount column, not Group


def test_to_numeric_strips_bold_markers():
    """Bold markdown markers should not break numeric parsing."""
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("**-₹4,83,350**") == -483350.0
    assert _to_numeric("**+₹5,64,700**") == 564700.0
    assert _to_numeric("**-27.3%**") == -27.3
    assert _to_numeric("**+216.8%**") == 216.8
    assert _to_numeric("**100.0%**") == 100.0


def test_format_pie_data_all_text_returns_empty():
    """Pie chart with no numeric columns returns empty list."""
    from backend.agents.chart_agent import _format_pie_data
    headers = ["Name", "Group", "Status"]
    rows = [
        ["Item A", "Electronics", "Active"],
        ["Item B", "Office Supplies", "Inactive"],
    ]
    data = _format_pie_data(headers, rows)
    assert data == []


def test_identify_numeric_columns_strips_bold():
    """_identify_numeric_columns should handle bold-marked values."""
    from backend.agents.chart_agent import _identify_numeric_columns
    headers = ["Metric", "Q3", "Q4"]
    rows = [
        ["Revenue", "**₹11,91,250**", "**₹8,66,400**"],
        ["Expenses", "**₹6,62,000**", "**₹6,81,000**"],
    ]
    result = _identify_numeric_columns(headers, rows)
    assert "Q3" in result
    assert "Q4" in result


def test_trim_trailing_zeros_also_trims_leading():
    """With only 2 nonzero rows (span < 3), Rule D preserves all rows for context."""
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Apr 2025", 0, "—", "—"],
        ["May 2025", 0, "+0.00", "N/A"],
        ["Jun 2025", 0, "+0.00", "N/A"],
        ["Jul 2025", 295000, "+295000.00", "N/A"],
        ["Aug 2025", 300000, "+5000.00", "+1.7%"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    # Span is 2 (Jul + Aug), which is < 3 — Rule D preserves all rows
    assert len(trimmed) == 5
    assert trimmed[0][0] == "Apr 2025"


# ---------------------------------------------------------------------------
# Tests: Rule A — Scale Mismatch Detection
# ---------------------------------------------------------------------------


class TestScaleMismatchDetection:
    def test_count_column_excluded_when_scale_mismatch(self):
        headers = ["Customer", "Invoices", "Total Sales Amount"]
        rows = [["Alice", 3, 708500], ["Bob", 2, 377000], ["Carol", 2, 275000]]
        config = _build_config("bar", headers, rows)
        assert "Total Sales Amount" in config["y_keys"]
        assert "Invoices" not in config["y_keys"]

    def test_vouchers_excluded_when_scale_mismatch(self):
        headers = ["Month", "Vouchers", "Sales Amount"]
        rows = [["Oct", 5, 544000], ["Nov", 3, 229500], ["Dec", 3, 417750]]
        config = _build_config("bar", headers, rows)
        assert "Sales Amount" in config["y_keys"]
        assert "Vouchers" not in config["y_keys"]

    def test_no_exclusion_when_same_scale(self):
        headers = ["Month", "Revenue", "Expenses"]
        rows = [["Q1", 500000, 400000], ["Q2", 600000, 450000]]
        config = _build_config("bar", headers, rows)
        assert "Revenue" in config["y_keys"]
        assert "Expenses" in config["y_keys"]


# ---------------------------------------------------------------------------
# Tests: Rule B — Percentage Value Detection
# ---------------------------------------------------------------------------


class TestPercentageValueDetection:
    def test_operating_margin_detected_as_secondary(self):
        assert _is_secondary_axis_column("Operating Profit Margin") is True

    def test_growth_rate_detected(self):
        assert _is_secondary_axis_column("Growth Rate") is True

    def test_margin_detected(self):
        assert _is_secondary_axis_column("Gross Margin") is True

    def test_ratio_detected(self):
        assert _is_secondary_axis_column("Debt-Equity Ratio") is True

    def test_regular_column_not_detected(self):
        assert _is_secondary_axis_column("Sales Amount") is False

    def test_existing_percent_still_works(self):
        assert _is_secondary_axis_column("Change %") is True


# ---------------------------------------------------------------------------
# Tests: Rule C — Enhanced Total Row Exclusion
# ---------------------------------------------------------------------------


class TestEnhancedTotalRowExclusion:
    def test_total_revenue_skipped(self):
        headers = ["Ledger", "Q3", "Q4"]
        rows = [
            ["Sales - Electronics", 1139500, 811400],
            ["Sales - Office Supplies", 51750, 55000],
            ["Total Revenue", 1191250, 866400],
        ]
        data = _format_xy_data(headers, rows)
        labels = [d["label"] for d in data]
        assert "Total Revenue" not in labels
        assert "Sales - Electronics" in labels

    def test_total_opex_skipped(self):
        headers = ["Ledger", "Amount"]
        rows = [["Rent", 150000], ["Salaries", 500000], ["Total OpEx", 650000]]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_grand_total_already_works(self):
        headers = ["Item", "Amount"]
        rows = [["A", 100], ["B", 200], ["Grand Total", 300]]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_net_total_skipped(self):
        headers = ["Item", "Amount"]
        rows = [["A", 100], ["B", 200], ["Net Total", 300]]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_bold_total_skipped(self):
        headers = ["Item", "Amount"]
        rows = [["A", 100], ["B", 200], ["**Total**", 300]]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_overall_skipped(self):
        headers = ["Item", "Amount"]
        rows = [["A", 100], ["B", 200], ["Overall", 300]]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Tests: Rule D — Smarter Zero Trimming
# ---------------------------------------------------------------------------


class TestSmarterZeroTrimming:
    def test_preserves_zeros_when_few_nonzero_points(self):
        headers = ["Month", "Sales"]
        rows = [
            ["Apr", 0], ["May", 0], ["Jun", 0], ["Jul", 0],
            ["Aug", 0], ["Sep", 0], ["Oct", 544000], ["Nov", 229500],
        ]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 8

    def test_trims_zeros_when_enough_nonzero(self):
        headers = ["Month", "Sales"]
        rows = [
            ["Jan", 0], ["Feb", 0], ["Mar", 0],
            ["Apr", 100], ["May", 200], ["Jun", 300], ["Jul", 400],
            ["Aug", 0], ["Sep", 0],
        ]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 4
        assert result[0][0] == "Apr"
        assert result[-1][0] == "Jul"

    def test_no_zeros_unchanged(self):
        headers = ["Month", "Sales"]
        rows = [["Jan", 100], ["Feb", 200], ["Mar", 300]]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 3
