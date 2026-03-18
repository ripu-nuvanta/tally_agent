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


def _make_stream_mock(response):
    """Create a mock that simulates anthropic_client.messages.stream() context manager."""
    mock_stream = AsyncMock()
    mock_stream.get_final_message = AsyncMock(return_value=response)

    mock_manager = MagicMock()
    mock_manager.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_manager.__aexit__ = AsyncMock(return_value=False)

    return mock_manager


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
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(
                _make_text_response(
                    "The total amount is ₹100.\n"
                    "- Only one item in the dataset\n"
                    "Chart suggestion: table_only"
                )
            ))
            result = await agent.execute(raw_data, None, "What is the total?", "aggregation")

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
            mock_claude.messages.stream = MagicMock(side_effect=[
                _make_stream_mock(tool_call), _make_stream_mock(final)
            ])
            result = await agent.execute(raw_data, None, "Top 3 customers", "top_n")

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
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(infinite_call))
            result = await agent.execute(raw_data, None, "Total?", "aggregation")

        assert len(result["tool_results"]) == 2
        assert "limit" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_insights_extracted_from_bullets(self):
        """Bullet points in Claude's response are extracted as insights."""
        agent = AnalysisAgent()

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(
                _make_text_response(
                    "Summary here.\n"
                    "- Revenue grew 20% QoQ\n"
                    "- Expenses remained flat\n"
                    "- Net profit improved\n"
                    "Chart suggestion: line"
                )
            ))
            result = await agent.execute([], None, "Show trend", "trend")

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
            mock_claude.messages.stream = MagicMock(side_effect=[
                _make_stream_mock(bad_call), _make_stream_mock(final)
            ])
            result = await agent.execute([], None, "Sort data", "top_n")

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
            mock_claude.messages.stream = MagicMock(side_effect=[
                _make_stream_mock(parallel), _make_stream_mock(final)
            ])
            result = await agent.execute(raw_data, None, "Sort and total", "aggregation")

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
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(parallel))
            result = await agent.execute(raw_data, None, "Analyze", "aggregation")

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
            mock_claude.messages.stream = MagicMock(
                side_effect=anthropic.APIConnectionError(request=MagicMock())
            )
            result = await agent.execute([], None, "Analyze", "aggregation")

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

from backend.agents.analysis_agent import _extract_chart_suggestion, _extract_chart_title


class TestExtractChartTitle:
    def test_basic_extraction(self):
        text = "Chart title: Monthly Revenue Trend"
        assert _extract_chart_title(text) == "Monthly Revenue Trend"

    def test_with_bold_markdown(self):
        text = "**Chart title:** Revenue by Region"
        assert _extract_chart_title(text) == "Revenue by Region"

    def test_underscore_variant(self):
        text = "Chart_title: Top 5"
        assert _extract_chart_title(text) == "Top 5"

    def test_no_title_present(self):
        text = "Here is the analysis.\nChart suggestion: bar"
        assert _extract_chart_title(text) is None

    def test_title_on_non_first_line(self):
        text = "Line one.\nLine two.\nChart title: Sales Breakdown\nLine four."
        assert _extract_chart_title(text) == "Sales Breakdown"

    def test_strips_enclosing_quotes(self):
        text = 'Chart title: "Quarterly Revenue"'
        assert _extract_chart_title(text) == "Quarterly Revenue"

    def test_strips_single_quotes(self):
        text = "Chart title: 'Top 5 Ledgers'"
        assert _extract_chart_title(text) == "Top 5 Ledgers"


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


def test_compute_trend_trailing_zero_shows_na():
    from backend.agents.analysis_agent import _tool_compute_trend
    series = [
        {"period": "Jan 2026", "value": 611850},
        {"period": "Feb 2026", "value": 0},
        {"period": "Mar 2026", "value": 0},
    ]
    result = _tool_compute_trend(series)
    rows = result["rows"]
    # Feb: 611850 → 0 should be N/A, not -100.0%
    assert rows[1][3] == "N/A"
    # Mar: 0 → 0 should also be N/A
    assert rows[2][3] == "N/A"


# ---------------------------------------------------------------------------
# Phase 6: _ensure_totals_row tests
# ---------------------------------------------------------------------------

class TestEnsureTotalsRow:
    def test_adds_total_for_top_n(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Customer", "Sales"]
        rows = [["Alice", 1000], ["Bob", 2000], ["Charlie", 3000]]
        result = _ensure_totals_row(headers, rows, "top_n")
        assert len(result) == 4
        assert result[-1][0] == "Total"
        assert result[-1][1] == 6000

    def test_skips_if_total_exists(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Customer", "Sales"]
        rows = [["Alice", 1000], ["Grand Total", 1000]]
        result = _ensure_totals_row(headers, rows, "top_n")
        assert len(result) == 2

    def test_adds_total_for_trend(self):
        """Trend queries should get a Total row."""
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Period", "Sales", "Change", "Change %"]
        rows = [
            ["Jul 2025", 295000, "—", "—"],
            ["Aug 2025", 300000, "+5000", "+1.7%"],
            ["Sep 2025", 300000, "+0", "0.0%"],
        ]
        result = _ensure_totals_row(headers, rows, "trend")
        assert len(result) == 4
        assert result[-1][0] == "Total"
        assert result[-1][1] == 895000
        assert result[-1][3] == ""  # % column skipped

    def test_handles_string_amounts(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Customer", "Sales"]
        rows = [["Alice", "₹1,000"], ["Bob", "₹2,000"]]
        result = _ensure_totals_row(headers, rows, "comparison")
        assert len(result) == 3
        assert result[-1][1] == 3000.0

    def test_skips_percentage_columns(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Item", "Amount", "Change %"]
        rows = [["A", 100, "10%"], ["B", 200, "20%"]]
        result = _ensure_totals_row(headers, rows, "comparison")
        assert result[-1][1] == 300
        assert result[-1][2] == ""  # % columns skipped

    def test_adds_total_for_aggregation(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        headers = ["Category", "Amount"]
        rows = [["Food", 500], ["Transport", 300]]
        result = _ensure_totals_row(headers, rows, "aggregation")
        assert len(result) == 3
        assert result[-1][0] == "Total"
        assert result[-1][1] == 800

    def test_empty_rows(self):
        from backend.agents.analysis_agent import _ensure_totals_row
        result = _ensure_totals_row(["A", "B"], [], "top_n")
        assert result == []


# ---------------------------------------------------------------------------
# Phase 8: _strip_chart_metadata tests
# ---------------------------------------------------------------------------

class TestStripChartMetadata:
    def test_chart_metadata_stripped_from_message(self):
        """Chart suggestion and Chart title lines should not appear in user-visible message."""
        from backend.agents.analysis_agent import _strip_chart_metadata
        text = """Here is the sales trend analysis.

Sales grew steadily from Jul to Dec 2025.

Chart suggestion: bar
Chart title: Monthly Sales Trend FY 2025-26"""
        result = _strip_chart_metadata(text)
        assert "Chart suggestion" not in result
        assert "Chart title" not in result
        assert "sales trend analysis" in result

    def test_strip_chart_metadata_with_bold_markdown(self):
        from backend.agents.analysis_agent import _strip_chart_metadata
        text = "Analysis complete.\n\n**Chart suggestion:** composed\n**Chart title:** Q2 vs Q3 Sales"
        result = _strip_chart_metadata(text)
        assert "Chart suggestion" not in result
        assert "Chart title" not in result
        assert "Analysis complete" in result


# ---------------------------------------------------------------------------
# Phase 8b: MAX_TOOL_CALLS default
# ---------------------------------------------------------------------------


def test_max_tool_calls_default_is_15():
    """Analysis agent should have a generous tool limit for multi-dataset queries."""
    from backend.agents.analysis_agent import MAX_TOOL_CALLS, AnalysisAgent
    assert MAX_TOOL_CALLS == 15
    agent = AnalysisAgent()
    assert agent.max_tool_calls == 15


@pytest.mark.asyncio
async def test_comparison_table_data_tracker_prefers_period_comparison():
    """For comparison queries, compute_period_comparison result is preferred over compute_totals."""
    agent = AnalysisAgent()
    raw_data = [
        {"label": "Sales", "value": 1000},
        {"label": "Expenses", "value": 500},
    ]

    # Turn 1: Claude calls compute_period_comparison → returns 2-row comparison table
    comparison_call = _make_tool_call_response(
        "compute_period_comparison",
        {
            "period_a": [{"label": "Sales", "value": 1000}, {"label": "Expenses", "value": 500}],
            "period_b": [{"label": "Sales", "value": 1200}, {"label": "Expenses", "value": 600}],
            "period_a_name": "Q2",
            "period_b_name": "Q3",
        },
        tool_use_id="tu_comp_1",
    )
    # Turn 2: Claude calls compute_totals → returns single aggregate row
    totals_call = _make_tool_call_response(
        "compute_totals",
        {
            "records": [{"amount": 216000}],
            "numeric_fields": ["amount"],
        },
        tool_use_id="tu_comp_2",
    )
    # Turn 3: Claude produces final text
    final = _make_text_response(
        "Q2 vs Q3 comparison complete.\n"
        "- Sales grew 20%\n"
        "- Expenses grew 20%\n"
        "Chart suggestion: grouped_bar\n"
        "Chart title: Q2 vs Q3 Comparison"
    )

    with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
        mock_claude.messages.stream = MagicMock(side_effect=[
            _make_stream_mock(comparison_call), _make_stream_mock(totals_call), _make_stream_mock(final)
        ])
        result = await agent.execute(raw_data, None, "Compare Q2 vs Q3", "comparison")

    # The comparison table (2 rows) should be preferred over the totals (1 row)
    assert len(result["tool_results"]) == 2
    data = result["data"]
    assert "Q2" in data["headers"]
    assert "Q3" in data["headers"]
    # Should have 2 data rows + 1 Total row (from _ensure_totals_row)
    data_rows = [r for r in data["rows"] if r[0] != "Total"]
    assert len(data_rows) == 2
    assert result["chart_suggestion"] == "grouped_bar"


# ---------------------------------------------------------------------------
# Task 7: Code Execution support in AnalysisAgent
# ---------------------------------------------------------------------------


class TestAnalysisAgentCodeExecution:
    def test_build_analysis_tools_code_exec_enabled(self):
        from backend.agents.analysis_agent import _build_analysis_tools
        tools = _build_analysis_tools(code_execution_enabled=True)
        tool_types = [t.get("type", "") for t in tools]
        assert "code_execution_20260120" in tool_types
        tool_names = [t.get("name", "") for t in tools if "name" in t]
        assert "compute_totals" not in tool_names

    def test_build_analysis_tools_code_exec_disabled(self):
        from backend.agents.analysis_agent import _build_analysis_tools
        tools = _build_analysis_tools(code_execution_enabled=False)
        tool_names = [t["name"] for t in tools]
        assert "compute_totals" in tool_names

    @pytest.mark.asyncio
    async def test_code_exec_captures_structured_table_data(self):
        """AnalysisAgent captures STRUCTURED_RESULT from code execution as table data."""
        from backend.agents.analysis_agent import AnalysisAgent

        response = MagicMock()
        response.stop_reason = "end_turn"
        text_block = MagicMock(type="text")
        text_block.text = "Top 5 items by sales.\n- Item A leads\nChart suggestion: bar\nChart title: Top Items"
        server_tool = MagicMock(type="server_tool_use")
        server_tool.input = {"code": "import json; print('STRUCTURED_RESULT:' + json.dumps({'headers':['Item','Sales'],'rows':[['A',100],['B',50]]}))"}
        code_result = MagicMock(type="code_execution_tool_result")
        code_result.stdout = 'STRUCTURED_RESULT:{"headers":["Item","Sales"],"rows":[["A",100],["B",50]]}\n'
        code_result.stderr = ""
        code_result.return_code = 0
        response.content = [text_block, server_tool, code_result]

        with (
            patch("backend.agents.analysis_agent.anthropic_client") as mock_claude,
            patch("backend.agents.analysis_agent.settings") as mock_settings,
        ):
            mock_settings.CLAUDE_MODEL = "test-model"
            mock_settings.CODE_EXECUTION_ENABLED = True
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(response))

            agent = AnalysisAgent()
            result = await agent.execute(
                raw_data=[{"item": "A", "amount": 100}],
                computed_data=None,
                user_query="top 5 items",
                query_type="top_n",
            )

        assert result["data"]["headers"] == ["Item", "Sales"]
        assert result["data"]["rows"][0] == ["A", 100]


# ---------------------------------------------------------------------------
# Tests: _parse_markdown_table fallback
# ---------------------------------------------------------------------------

from backend.agents.analysis_agent import _parse_markdown_table


class TestParseMarkdownTable:
    def test_parses_simple_table(self):
        text = """Here are the results:

| Month | Sales | Change % |
|-------|-------|----------|
| Oct | 5,00,000 | 10.0 |
| Nov | 4,50,000 | -10.0 |
"""
        result = _parse_markdown_table(text)
        assert result is not None
        assert result["headers"] == ["Month", "Sales", "Change %"]
        assert len(result["rows"]) == 2
        assert result["rows"][0] == ["Oct", "5,00,000", "10.0"]

    def test_uses_last_table_when_multiple(self):
        text = """Summary:
| Category | Total |
|----------|-------|
| Sales | 100 |

Details:
| Month | Amount | Growth |
|-------|--------|--------|
| Jan | 50 | 5% |
| Feb | 50 | 0% |
"""
        result = _parse_markdown_table(text)
        assert result["headers"] == ["Month", "Amount", "Growth"]
        assert len(result["rows"]) == 2

    def test_returns_none_for_no_table(self):
        text = "No tables here, just text."
        assert _parse_markdown_table(text) is None

    def test_returns_none_for_incomplete_table(self):
        text = "| Header |\n|--------|\n"  # no data rows
        assert _parse_markdown_table(text) is None

    def test_handles_total_row(self):
        text = """| Ledger | Q3 | Q4 | Change |
|--------|-----|-----|--------|
| Sales | 10,00,000 | 12,00,000 | 2,00,000 |
| Purchases | 5,00,000 | 6,00,000 | 1,00,000 |
| Total | 15,00,000 | 18,00,000 | 3,00,000 |
"""
        result = _parse_markdown_table(text)
        assert len(result["rows"]) == 3
        assert result["rows"][2][0] == "Total"

    def test_strips_whitespace_from_cells(self):
        text = """|  Name  |  Amount  |
|-------|----------|
|  Alice  |  1000  |
"""
        result = _parse_markdown_table(text)
        assert result["rows"][0] == ["Alice", "1000"]

    def test_handles_alignment_separators(self):
        """Separator with colons for alignment (e.g., |:---:|) should still parse."""
        text = """| Name | Amount |
|:-----|-------:|
| Bob | 2000 |
"""
        result = _parse_markdown_table(text)
        assert result is not None
        assert result["headers"] == ["Name", "Amount"]
        assert result["rows"][0] == ["Bob", "2000"]

    def test_returns_none_for_empty_text(self):
        assert _parse_markdown_table("") is None
        assert _parse_markdown_table("   \n\n  ") is None

    def test_pads_short_rows(self):
        """Rows with fewer cells than headers should be padded."""
        text = """| A | B | C |
|---|---|---|
| 1 | 2 |
"""
        result = _parse_markdown_table(text)
        assert result is not None
        # The row "| 1 | 2 |" splits to ["1", "2"], padded to ["1", "2", ""]
        assert result["rows"][0] == ["1", "2", ""]


class TestMarkdownTableFallbackIntegration:
    """Test that the markdown table fallback fires in the AnalysisAgent loop."""

    @pytest.mark.asyncio
    async def test_markdown_fallback_captures_table_when_no_structured_result(self):
        """When code_execution is disabled and no STRUCTURED_RESULT, markdown table is captured."""
        agent = AnalysisAgent()

        md_response = _make_text_response(
            "Here is the monthly breakdown:\n\n"
            "| Month | Sales | Change % |\n"
            "|-------|-------|----------|\n"
            "| Oct | 5,00,000 | 10.0 |\n"
            "| Nov | 4,50,000 | -10.0 |\n\n"
            "Chart suggestion: bar\n"
            "Chart title: Monthly Sales"
        )

        with (
            patch("backend.agents.analysis_agent.anthropic_client") as mock_claude,
            patch("backend.agents.analysis_agent.settings") as mock_settings,
        ):
            mock_settings.CLAUDE_MODEL = "test-model"
            mock_settings.CODE_EXECUTION_ENABLED = False
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(md_response))

            result = await agent.execute(
                raw_data=[{"month": "Oct", "sales": 500000}],
                computed_data=None,
                user_query="monthly sales breakdown",
                query_type="trend",
            )

        assert result["data"]["headers"] == ["Month", "Sales", "Change %"]
        assert len(result["data"]["rows"]) >= 2
        assert result["data"]["rows"][0][0] == "Oct"

    @pytest.mark.asyncio
    async def test_structured_result_preferred_over_markdown(self):
        """STRUCTURED_RESULT text fallback takes priority over markdown table."""
        agent = AnalysisAgent()

        structured_json = json.dumps({"headers": ["X", "Y"], "rows": [["a", 1]]})
        text_with_both = (
            f"STRUCTURED_RESULT:{structured_json}\n\n"
            "| Month | Sales |\n"
            "|-------|-------|\n"
            "| Oct | 500 |\n\n"
            "Chart suggestion: bar"
        )
        response = _make_text_response(text_with_both)

        with (
            patch("backend.agents.analysis_agent.anthropic_client") as mock_claude,
            patch("backend.agents.analysis_agent.settings") as mock_settings,
        ):
            mock_settings.CLAUDE_MODEL = "test-model"
            mock_settings.CODE_EXECUTION_ENABLED = True
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(response))

            result = await agent.execute(
                raw_data=[],
                computed_data=None,
                user_query="test",
                query_type="aggregation",
            )

        # STRUCTURED_RESULT should win
        assert result["data"]["headers"] == ["X", "Y"]


def test_parse_markdown_table_strips_bold():
    """Bold markers in markdown table cells should be stripped."""
    from backend.agents.analysis_agent import _parse_markdown_table
    text = '''
| Metric | Q3 | Q4 | Change % |
|---|---|---|---|
| Revenue | ₹11,91,250 | ₹8,66,400 | **-27.3%** |
| Gross Profit | **-₹4,83,350** | **+₹5,64,700** | **+216.8%** |
'''
    result = _parse_markdown_table(text)
    assert result is not None
    # Bold markers should be stripped
    assert result["rows"][1][1] == "-₹4,83,350"
    assert result["rows"][1][2] == "+₹5,64,700"
    assert result["rows"][0][3] == "-27.3%"


# ---------------------------------------------------------------------------
# Phase 14: Session context injection
# ---------------------------------------------------------------------------


class TestAnalysisAgentSessionContext:
    @pytest.mark.asyncio
    async def test_execute_receives_session_context(self):
        """AnalysisAgent.execute() includes prior session messages when session is provided."""
        from backend.agents.context import SessionContext

        session = SessionContext()
        session.add_message("user", "Show monthly sales for this FY")
        session.add_message("assistant", "Monthly sales: Jul ₹2,95,000 / Aug ₹3,00,000")

        agent = AnalysisAgent()
        captured = {}

        def mock_stream(**kwargs):
            captured["messages"] = kwargs["messages"]
            return _make_stream_mock(_make_text_response("The average monthly sales is ₹4,16,483."))

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.stream = MagicMock(side_effect=mock_stream)
            result = await agent.execute(
                raw_data=[{"account_name": "Sales", "closing_balance": 100000}],
                computed_data=None,
                user_query="What is the average monthly sales?",
                query_type="aggregation",
                session=session,
            )

        assert "messages" in captured
        user_content = captured["messages"][0]["content"]
        assert "Prior Conversation Context" in user_content
        assert "monthly sales" in user_content.lower()

    @pytest.mark.asyncio
    async def test_execute_works_without_session(self):
        """AnalysisAgent.execute() still works when session is None (backward compat)."""
        agent = AnalysisAgent()

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(
                _make_text_response("Total sales: ₹10,00,000.")
            ))
            result = await agent.execute(
                raw_data=[{"account_name": "Sales", "closing_balance": 1000000}],
                computed_data=None,
                user_query="What are total sales?",
                query_type="aggregation",
            )

        assert "message" in result
        assert "10,00,000" in result["message"]

    @pytest.mark.asyncio
    async def test_session_context_excludes_current_turn(self):
        """AnalysisAgent prompt includes prior turns but NOT the current turn's query/response.

        Since Orchestrator adds messages AFTER AnalysisAgent completes, the session
        passed to AnalysisAgent should only contain prior turns.  This test simulates
        a second turn where session has one prior turn (turn 1), and verifies:
        1. The prior turn IS in the prompt context
        2. The current turn's user query is in the prompt (as the active query, not context)
        3. The current turn's QueryAgent text is NOT in the context
        """
        from backend.agents.context import SessionContext

        session = SessionContext()
        # Prior turn (turn 1) — already in session before AnalysisAgent runs
        session.add_message("user", "Show monthly sales for this FY")
        session.add_message("assistant", "Monthly sales: Jul ₹2,95,000 / Aug ₹3,00,000")
        # Current turn (turn 2) is NOT added to session yet — Orchestrator adds it after

        agent = AnalysisAgent()
        captured = {}

        def mock_stream(**kwargs):
            captured["messages"] = kwargs["messages"]
            return _make_stream_mock(_make_text_response("The average monthly sales is ₹4,16,483."))

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.stream = MagicMock(side_effect=mock_stream)
            await agent.execute(
                raw_data=[{"account_name": "Sales", "closing_balance": 100000}],
                computed_data=None,
                user_query="What is the average monthly sales?",
                query_type="aggregation",
                session=session,
            )

        user_content = captured["messages"][0]["content"]

        # Prior turn IS in context
        assert "Prior Conversation Context" in user_content
        assert "Monthly sales: Jul" in user_content

        # Extract just the context block (between "Prior Conversation Context" header and
        # the next section starting with "User query:" which is the active query)
        context_start = user_content.index("Prior Conversation Context")
        # The active query line "User query: ..." marks end of context section
        active_query_start = user_content.index("User query:")
        context_section = user_content[context_start:active_query_start]

        # Context should contain the prior turn's messages
        assert "Show monthly sales for this FY" in context_section
        assert "Monthly sales: Jul" in context_section

        # Context should NOT contain the current turn's query text
        assert "average monthly sales" not in context_section

        # The active query line should contain the current query (outside context section)
        active_line = user_content[active_query_start:user_content.index("\n", active_query_start)]
        assert "What is the average monthly sales" in active_line

    @pytest.mark.asyncio
    async def test_session_context_includes_8_messages_truncated_at_1500(self):
        """Context building includes up to 8 messages, each truncated at 1500 chars."""
        from backend.agents.context import SessionContext

        session = SessionContext()
        # Add 12 messages — only the last 8 should be included
        for i in range(12):
            role = "user" if i % 2 == 0 else "assistant"
            session.add_message(role, f"Message {i}: " + "x" * 2000)

        agent = AnalysisAgent()
        captured = {}

        def mock_stream(**kwargs):
            captured["messages"] = kwargs["messages"]
            return _make_stream_mock(_make_text_response("Done."))

        with patch("backend.agents.analysis_agent.anthropic_client") as mock_claude:
            mock_claude.messages.stream = MagicMock(side_effect=mock_stream)
            await agent.execute(
                raw_data=[{"account_name": "Sales", "closing_balance": 100000}],
                computed_data=None,
                user_query="Summary?",
                query_type="aggregation",
                session=session,
            )

        user_content = captured["messages"][0]["content"]
        assert "Prior Conversation Context" in user_content

        # Exactly 8 messages included (messages 4-11), not the first 4
        for i in range(4, 12):
            assert f"Message {i}:" in user_content
        for i in range(4):
            assert f"Message {i}:" not in user_content

        # Each message truncated at 1500 chars — no 2000-char 'x' runs
        # Original content is "Message N: " + "x"*2000 = 2012 chars
        # After truncation at 1500, each entry has at most 1500 chars of content
        context_section = user_content.split("Prior Conversation Context")[1].split("## ")[0]
        entries = [e.strip() for e in context_section.split("\n\n") if e.strip()]
        for entry in entries:
            # Strip "User: " or "Assistant: " prefix to get the content portion
            if ": " in entry:
                content_part = entry.split(": ", 1)[1]
                assert len(content_part) <= 1500


# ---------------------------------------------------------------------------
# Fix: extract_text returns last text block (commit 7f91a31)
# ---------------------------------------------------------------------------


class TestAnalysisAgentLastTextBlock:
    """Integration-level test: AnalysisAgent returns the LAST text block content
    when the Claude API response contains multiple text blocks (code_execution)."""

    @pytest.mark.asyncio
    async def test_code_exec_returns_last_text_block_not_preamble(self):
        """When Claude returns text + server_tool_use + code_result + text,
        the AnalysisAgent's message should contain the LAST text block (the answer),
        not the preamble 'Let me compute...'."""
        from backend.agents.analysis_agent import AnalysisAgent

        preamble = "Let me compute the monthly averages for you."
        answer = "Here are the results: The average monthly sales is ₹4,16,483."

        response = MagicMock()
        response.stop_reason = "end_turn"

        # Block 1: preamble text
        text_block_1 = MagicMock(type="text")
        text_block_1.text = preamble

        # Block 2: server_tool_use (code_execution)
        server_tool = MagicMock(type="server_tool_use")
        server_tool.input = {"code": "print('hello')"}

        # Block 3: code_execution_tool_result
        code_result = MagicMock(type="code_execution_tool_result")
        code_result.stdout = "hello\n"
        code_result.stderr = ""
        code_result.return_code = 0

        # Block 4: final answer text
        text_block_2 = MagicMock(type="text")
        text_block_2.text = answer + "\nChart suggestion: table_only"

        response.content = [text_block_1, server_tool, code_result, text_block_2]

        with (
            patch("backend.agents.analysis_agent.anthropic_client") as mock_claude,
            patch("backend.agents.analysis_agent.settings") as mock_settings,
        ):
            mock_settings.CLAUDE_MODEL = "test-model"
            mock_settings.CODE_EXECUTION_ENABLED = True
            mock_claude.messages.stream = MagicMock(return_value=_make_stream_mock(response))

            agent = AnalysisAgent()
            result = await agent.execute(
                raw_data=[{"account_name": "Sales", "closing_balance": 100000}],
                computed_data=None,
                user_query="What is the average monthly sales?",
                query_type="aggregation",
            )

        # The message should contain the LAST text block (the answer)
        assert "average monthly sales" in result["message"]
        assert "₹4,16,483" in result["message"]
        # The preamble should NOT be in the returned message
        assert "Let me compute" not in result["message"]
