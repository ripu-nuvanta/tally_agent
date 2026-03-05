"""Unit tests for ChartAgent — rule-based chart type selection and data formatting.

Pure Python, no mocking needed — all tests are deterministic.
"""

import pytest

from backend.agents.chart_agent import ChartAgent, _to_numeric, _select_chart_type


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

    def test_table_only_suggestion_defers_to_query_type(self):
        rows = [[1], [2], [3]]
        assert _select_chart_type("table_only", "comparison", rows) == "grouped_bar"


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

    def test_grouped_bar_for_comparison(self):
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
        assert result["chart_type"] == "grouped_bar"
        assert result["data"][0]["Q1"] == 10000.0
        assert result["data"][0]["Q2"] == 12000.0

    def test_line_chart_for_trend(self):
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
        assert result["chart_type"] == "line"
        assert len(result["data"]) == 4

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
