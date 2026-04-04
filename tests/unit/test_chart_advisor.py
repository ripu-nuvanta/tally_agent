"""Unit tests for chart advisor — mock the Haiku API call."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agents.chart_advisor import get_chart_advice, _format_tables_for_prompt


class TestFormatTablesForPrompt:
    def test_single_table(self):
        tables = [{"headers": ["Month", "Sales"], "rows": [["Jan", 100], ["Feb", 200]]}]
        result = _format_tables_for_prompt(tables)
        assert "Table 0" in result
        assert "| Month | Sales |" in result
        assert "2 rows" in result

    def test_multiple_tables(self):
        tables = [
            {"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]},
            {"headers": ["C", "D"], "rows": [["p", 3], ["q", 4], ["r", 5]]},
        ]
        result = _format_tables_for_prompt(tables)
        assert "Table 0" in result
        assert "Table 1" in result
        assert "3 rows" in result

    def test_truncates_long_tables(self):
        tables = [{"headers": ["X", "Y"], "rows": [[f"r{i}", i] for i in range(15)]}]
        result = _format_tables_for_prompt(tables)
        assert "5 more rows" in result


def _make_mock_response(tool_input: dict):
    """Create a mock Anthropic response with a tool_use block."""
    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.input = tool_input
    mock_resp.content = [mock_block]
    mock_resp.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_resp


def _make_mock_text_response(text: str):
    """Create a mock Anthropic response with text (for error cases)."""
    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = text
    mock_resp.content = [mock_block]
    mock_resp.usage = MagicMock(input_tokens=100, output_tokens=50)
    return mock_resp


class TestGetChartAdvice:
    @pytest.mark.asyncio
    async def test_returns_valid_advice(self):
        advice = {
            "table_index": 0,
            "x_column": "Customer",
            "y_columns": ["Sales"],
            "secondary_y_columns": [],
            "chart_type": "bar",
            "chart_title": "Top Customers",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, usage = await get_chart_advice(
                [{"headers": ["Customer", "Sales"], "rows": [["A", 100], ["B", 200]]}],
                "top customers",
            )
        assert result is not None
        assert result["x_column"] == "Customer"
        assert result["y_columns"] == ["Sales"]
        assert result["chart_type"] == "bar"
        assert usage is not None
        assert usage["agent"] == "chart_advisor"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_tables(self):
        result, usage = await get_chart_advice([], "some query")
        assert result is None
        assert usage is None

    @pytest.mark.asyncio
    async def test_returns_none_on_no_tool_block(self):
        """Returns None when response contains no tool_use block."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_mock_text_response("I cannot select a chart for this data.")
        )

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, usage = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is None
        assert usage is not None  # Usage still tracked even on failure

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_fields(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_mock_response({"table_index": 0})
        )

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, usage = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is None
        assert usage is not None

    @pytest.mark.asyncio
    async def test_validates_table_index(self):
        advice = {
            "table_index": 5,
            "x_column": "A",
            "y_columns": ["B"],
            "chart_type": "bar",
            "chart_title": "Test",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, usage = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is not None
        assert result["table_index"] == 0  # Corrected to valid index

    @pytest.mark.asyncio
    async def test_normalizes_string_y_columns(self):
        advice = {
            "table_index": 0,
            "x_column": "Name",
            "y_columns": "Amount",
            "chart_type": "bar",
            "chart_title": "Test",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, _ = await get_chart_advice(
                [{"headers": ["Name", "Amount"], "rows": [["A", 100], ["B", 200]]}],
                "query",
            )
        assert result["y_columns"] == ["Amount"]

    @pytest.mark.asyncio
    async def test_passes_chart_suggestion(self):
        advice = {
            "table_index": 0,
            "x_column": "Category",
            "y_columns": ["Amount"],
            "chart_type": "pie",
            "chart_title": "Breakdown",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result, _ = await get_chart_advice(
                [{"headers": ["Category", "Amount"], "rows": [["A", 100], ["B", 200]]}],
                "breakdown",
                chart_suggestion="pie",
            )
        # Verify the suggestion was passed to the API
        call_args = mock_client.messages.create.call_args
        user_content = call_args.kwargs["messages"][0]["content"]
        assert "Suggested chart type (from analysis agent — override if needed): pie" in user_content
        # Verify tools were passed
        assert "tools" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_passes_tool_choice(self):
        """Verify tool_choice forces select_chart tool."""
        advice = {
            "table_index": 0, "x_column": "A", "y_columns": ["B"],
            "chart_type": "bar", "chart_title": "Test",
        }
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "select_chart"}
