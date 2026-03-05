"""Unit tests for AnalysisAgent — Claude tool-calling loop with Python analysis tools.

Tests the analysis computation tools (pure Python, no mocking needed) and the
Claude-based agent loop (mocked API calls).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.analysis_agent import (
    AnalysisAgent,
    execute_analysis_tool,
    _tool_sort_by_field,
    _tool_compute_totals,
    _tool_compute_percentage_change,
    _tool_compute_period_comparison,
    _tool_compute_trend,
)


# ---------------------------------------------------------------------------
# Helper factories for mock Claude responses
# ---------------------------------------------------------------------------


def _make_text_response(text: str):
    """Mock Claude response with just text (end_turn)."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    return msg


def _make_tool_call_response(
    tool_name: str, tool_input: dict, tool_use_id: str = "tu_analysis_1"
):
    """Mock Claude response requesting an analysis tool call."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_use_id
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = ""
    msg.content = [text_block, tool_block]
    return msg


# ---------------------------------------------------------------------------
# Tests: Pure Python analysis tools
# ---------------------------------------------------------------------------


class TestSortByField:
    def test_sort_descending(self):
        records = [{"name": "A", "amount": 100}, {"name": "B", "amount": 300}, {"name": "C", "amount": 200}]
        result = _tool_sort_by_field(records, "amount", descending=True, label_field="name")
        assert result["rows"][0] == ["B", 300]
        assert result["rows"][-1] == ["A", 100]

    def test_sort_ascending(self):
        records = [{"name": "A", "amount": 100}, {"name": "B", "amount": 300}]
        result = _tool_sort_by_field(records, "amount", descending=False, label_field="name")
        assert result["rows"][0] == ["A", 100]

    def test_sort_with_limit(self):
        records = [{"x": 1}, {"x": 3}, {"x": 2}, {"x": 5}, {"x": 4}]
        result = _tool_sort_by_field(records, "x", descending=True, limit=3)
        assert len(result["rows"]) == 3
        assert result["records"][0]["x"] == 5

    def test_sort_no_label_field(self):
        records = [{"amount": 50}, {"amount": 100}]
        result = _tool_sort_by_field(records, "amount")
        assert result["headers"] == ["amount"]

    def test_sort_missing_field_treated_as_zero(self):
        records = [{"name": "A", "amount": 100}, {"name": "B"}]
        result = _tool_sort_by_field(records, "amount", descending=True, label_field="name")
        assert result["rows"][0] == ["A", 100]


class TestComputeTotals:
    def test_simple_sum(self):
        records = [{"amount": 100}, {"amount": 200}, {"amount": 300}]
        result = _tool_compute_totals(records, ["amount"])
        assert result["records"][0]["amount"] == 600.0

    def test_multiple_fields(self):
        records = [{"debit": 100, "credit": 50}, {"debit": 200, "credit": 150}]
        result = _tool_compute_totals(records, ["debit", "credit"])
        assert result["records"][0]["debit"] == 300.0
        assert result["records"][0]["credit"] == 200.0

    def test_group_by(self):
        records = [
            {"type": "Sales", "amount": 100},
            {"type": "Sales", "amount": 200},
            {"type": "Purchase", "amount": 50},
        ]
        result = _tool_compute_totals(records, ["amount"], group_by="type")
        by_type = {r["type"]: r["amount"] for r in result["records"]}
        assert by_type["Sales"] == 300.0
        assert by_type["Purchase"] == 50.0

    def test_missing_values_treated_as_zero(self):
        records = [{"amount": 100}, {"other": 50}]
        result = _tool_compute_totals(records, ["amount"])
        assert result["records"][0]["amount"] == 100.0


class TestComputePercentageChange:
    def test_increase(self):
        result = _tool_compute_percentage_change(100.0, 150.0, "Revenue")
        assert result["absolute_change"] == 50.0
        assert result["percentage_change"] == pytest.approx(50.0)
        assert result["direction"] == "increase"

    def test_decrease(self):
        result = _tool_compute_percentage_change(200.0, 150.0, "Expenses")
        assert result["absolute_change"] == -50.0
        assert result["percentage_change"] == pytest.approx(-25.0)
        assert result["direction"] == "decrease"

    def test_no_change(self):
        result = _tool_compute_percentage_change(100.0, 100.0)
        assert result["absolute_change"] == 0.0
        assert result["direction"] == "no change"

    def test_zero_base(self):
        result = _tool_compute_percentage_change(0.0, 100.0)
        assert result["percentage_change"] is None
        assert "N/A" in result["percentage_change_str"]


class TestComputePeriodComparison:
    def test_basic_comparison(self):
        period_a = [{"label": "Sales", "value": 1000}, {"label": "Expenses", "value": 500}]
        period_b = [{"label": "Sales", "value": 1200}, {"label": "Expenses", "value": 600}]
        result = _tool_compute_period_comparison(period_a, period_b, "Q1", "Q2")
        assert result["headers"] == ["Item", "Q1", "Q2", "Change", "Change %"]
        # Sales row
        sales_row = result["rows"][0]
        assert sales_row[0] == "Sales"
        assert sales_row[1] == 1000.0
        assert sales_row[2] == 1200.0
        assert sales_row[3] == 200.0

    def test_missing_label_in_one_period(self):
        period_a = [{"label": "Sales", "value": 1000}]
        period_b = [{"label": "Sales", "value": 1200}, {"label": "New Item", "value": 300}]
        result = _tool_compute_period_comparison(period_a, period_b, "Q1", "Q2")
        assert len(result["rows"]) == 2
        new_row = [r for r in result["rows"] if r[0] == "New Item"][0]
        assert new_row[1] == 0.0  # Q1 value
        assert new_row[2] == 300.0  # Q2 value

    def test_custom_keys(self):
        period_a = [{"name": "Cash", "amount": 5000}]
        period_b = [{"name": "Cash", "amount": 7000}]
        result = _tool_compute_period_comparison(
            period_a, period_b, "Jan", "Feb",
            label_key="name", value_key="amount",
        )
        assert result["rows"][0][0] == "Cash"
        assert result["rows"][0][3] == 2000.0


class TestComputeTrend:
    def test_basic_trend(self):
        series = [
            {"period": "Jan", "value": 100},
            {"period": "Feb", "value": 120},
            {"period": "Mar", "value": 150},
        ]
        result = _tool_compute_trend(series)
        assert len(result["rows"]) == 3
        # First row has no change
        assert result["records"][0]["abs_change"] is None
        # Second row: 120 - 100 = 20
        assert result["records"][1]["abs_change"] == 20.0
        assert result["records"][1]["pct_change"] == pytest.approx(20.0)

    def test_custom_keys(self):
        series = [{"month": "Apr", "sales": 1000}, {"month": "May", "sales": 1500}]
        result = _tool_compute_trend(series, period_key="month", value_key="sales", value_label="Sales")
        assert result["headers"] == ["Period", "Sales", "Change", "Change %"]
        assert result["records"][1]["abs_change"] == 500.0

    def test_zero_previous_value(self):
        series = [{"period": "P1", "value": 0}, {"period": "P2", "value": 100}]
        result = _tool_compute_trend(series)
        assert result["records"][1]["pct_change"] is None


# ---------------------------------------------------------------------------
# Tests: execute_analysis_tool dispatcher
# ---------------------------------------------------------------------------


class TestExecuteAnalysisTool:
    def test_known_tool(self):
        result = execute_analysis_tool("compute_percentage_change", {
            "old_value": 100, "new_value": 150,
        })
        assert result["success"] is True
        assert result["data"]["absolute_change"] == 50.0

    def test_unknown_tool(self):
        result = execute_analysis_tool("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown" in result["error"]

    def test_bad_arguments(self):
        result = execute_analysis_tool("sort_by_field", {"wrong_param": True})
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: AnalysisAgent Claude loop
# ---------------------------------------------------------------------------


class TestAnalysisAgentLoop:
    @pytest.mark.asyncio
    async def test_direct_text_response(self):
        """Claude responds without calling any tools."""
        agent = AnalysisAgent()
        raw_data = [{"name": "A", "amount": 100}]

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_text_response(
                    "The total amount is ₹100.\n"
                    "- Only one item in the dataset\n"
                    "Chart suggestion: table_only"
                )
            )
            result = await agent.execute(raw_data, "What is the total?", "aggregation")

        assert "₹100" in result["message"]
        assert result["tool_results"] == []
        assert result["chart_suggestion"] == "table_only"

    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """Claude calls sort_by_field, then responds with text."""
        agent = AnalysisAgent()
        raw_data = [
            {"name": "Customer A", "amount": 500},
            {"name": "Customer B", "amount": 300},
            {"name": "Customer C", "amount": 800},
        ]

        tool_call = _make_tool_call_response(
            "sort_by_field",
            {
                "records": raw_data,
                "field": "amount",
                "descending": True,
                "limit": 3,
                "label_field": "name",
            },
        )
        final = _make_text_response(
            "Top 3 customers by amount:\n"
            "- Customer C leads with ₹800\n"
            "- Customer A follows with ₹500\n"
            "- Customer B at ₹300\n"
            "Chart suggestion: bar"
        )

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(side_effect=[tool_call, final])
            result = await agent.execute(raw_data, "Top 3 customers", "top_n")

        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool_name"] == "sort_by_field"
        assert result["data"]["headers"] == ["name", "amount"]
        assert result["data"]["rows"][0] == ["Customer C", 800]
        assert result["chart_suggestion"] == "bar"

    @pytest.mark.asyncio
    async def test_max_tool_calls_safety(self):
        """Agent stops after max_tool_calls."""
        agent = AnalysisAgent(max_tool_calls=2)
        raw_data = [{"amount": 100}]

        infinite_call = _make_tool_call_response(
            "compute_totals",
            {"records": raw_data, "numeric_fields": ["amount"]},
        )

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=infinite_call)
            result = await agent.execute(raw_data, "Total?", "aggregation")

        assert len(result["tool_results"]) == 2
        assert "limit" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_insights_extracted_from_bullets(self):
        """Bullet points in Claude's response are extracted as insights."""
        agent = AnalysisAgent()

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_text_response(
                    "Summary here.\n"
                    "- Revenue grew 20% QoQ\n"
                    "- Expenses remained flat\n"
                    "- Net profit improved\n"
                    "Chart suggestion: line"
                )
            )
            result = await agent.execute([], "Show trend", "trend")

        assert len(result["insights"]) == 3
        assert "Revenue grew 20% QoQ" in result["insights"]

    @pytest.mark.asyncio
    async def test_tool_error_passed_to_claude(self):
        """When an analysis tool errors, the error is sent back to Claude."""
        agent = AnalysisAgent()

        # First: Claude calls a tool with bad args
        bad_call = _make_tool_call_response(
            "sort_by_field",
            {"records": "not a list", "field": "amount"},
        )
        # Second: Claude gets error and responds with text
        final = _make_text_response("I encountered an error sorting. The data is: ₹100.")

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(side_effect=[bad_call, final])
            result = await agent.execute([], "Sort data", "top_n")

        assert len(result["tool_results"]) == 1
        assert "error" in result["tool_results"][0]["result"]


# ---------------------------------------------------------------------------
# Tests: Parallel analysis tool calls (Fix #1)
# ---------------------------------------------------------------------------


def _make_parallel_analysis_response(tools: list[tuple[str, dict, str]]):
    """Mock Claude response with multiple analysis tool_use blocks."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    blocks = []
    for tool_name, tool_input, tool_id in tools:
        block = MagicMock()
        block.type = "tool_use"
        block.name = tool_name
        block.input = tool_input
        block.id = tool_id
        blocks.append(block)
    msg.content = blocks
    return msg


class TestAnalysisAgentParallelCalls:
    @pytest.mark.asyncio
    async def test_parallel_analysis_tools_all_processed(self):
        """When Claude returns 2 analysis tool calls, both are executed."""
        agent = AnalysisAgent(max_tool_calls=8)
        raw_data = [{"account": "Sales", "amount": 100}, {"account": "Purchase", "amount": 50}]

        parallel = _make_parallel_analysis_response([
            ("sort_by_field", {"records": raw_data, "field": "amount", "descending": True}, "tu_p1"),
            ("compute_totals", {"records": raw_data, "numeric_fields": ["amount"]}, "tu_p2"),
        ])
        final = _make_text_response("Sorted and totaled.\n- Sales is highest\nChart suggestion: bar")

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(side_effect=[parallel, final])
            result = await agent.execute(raw_data, "Sort and total", "aggregation")

        assert len(result["tool_results"]) == 2
        assert result["tool_results"][0]["tool_name"] == "sort_by_field"
        assert result["tool_results"][1]["tool_name"] == "compute_totals"

    @pytest.mark.asyncio
    async def test_parallel_calls_count_toward_limit(self):
        """Parallel calls count by number of blocks, not iterations."""
        agent = AnalysisAgent(max_tool_calls=2)
        raw_data = [{"x": 1}]

        parallel = _make_parallel_analysis_response([
            ("sort_by_field", {"records": raw_data, "field": "x"}, "tu_1"),
            ("compute_totals", {"records": raw_data, "numeric_fields": ["x"]}, "tu_2"),
        ])

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=parallel)
            result = await agent.execute(raw_data, "Analyze", "aggregation")

        assert len(result["tool_results"]) == 2
        assert "limit" in result["message"].lower()


# ---------------------------------------------------------------------------
# Tests: Claude API error handling (Fix #3)
# ---------------------------------------------------------------------------


class TestAnalysisAgentAPIError:
    @pytest.mark.asyncio
    async def test_api_error_returns_graceful_result(self):
        """When Claude API fails, analysis agent returns partial result."""
        import anthropic

        agent = AnalysisAgent()

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                side_effect=anthropic.APIConnectionError(request=MagicMock())
            )
            result = await agent.execute([], "Analyze", "aggregation")

        assert "could not be completed" in result["message"].lower()
        assert "data" in result
        assert "insights" in result


# ---------------------------------------------------------------------------
# Tests: Logging on tool errors (Fix #7)
# ---------------------------------------------------------------------------


class TestAnalysisToolLogging:
    def test_execute_analysis_tool_logs_exception(self):
        """Issue #7: execute_analysis_tool must log exceptions before returning error."""
        import logging

        with patch("backend.agents.analysis_agent.logger") as mock_logger:
            result = execute_analysis_tool(
                "sort_by_field",
                {"records": "not-a-list", "field": "x"},
            )

        assert "error" in result
        mock_logger.exception.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _extract_chart_suggestion (Fix #15)
# ---------------------------------------------------------------------------

from backend.agents.analysis_agent import _extract_chart_suggestion


class TestExtractChartSuggestion:
    def test_grouped_bar_with_space(self):
        text = "Here is the analysis.\nChart suggestion: grouped bar"
        assert _extract_chart_suggestion(text) == "grouped_bar"

    def test_stacked_bar_with_space(self):
        text = "Summary of data.\nChart suggestion: stacked bar"
        assert _extract_chart_suggestion(text) == "stacked_bar"

    def test_single_word_still_works(self):
        text = "Results are ready.\nChart suggestion: bar"
        assert _extract_chart_suggestion(text) == "bar"

    def test_table_only_with_space(self):
        text = "No visual needed.\nChart suggestion: table only"
        assert _extract_chart_suggestion(text) == "table_only"
