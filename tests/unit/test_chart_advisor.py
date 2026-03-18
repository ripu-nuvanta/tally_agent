"""Unit tests for chart advisor — mock the Haiku API call."""

import json
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


def _make_mock_response(content: str):
    """Create a mock Anthropic response."""
    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.text = content
    mock_resp.content = [mock_block]
    return mock_resp


class TestGetChartAdvice:
    @pytest.mark.asyncio
    async def test_returns_valid_advice(self):
        advice_json = json.dumps({
            "table_index": 0,
            "x_column": "Customer",
            "y_columns": ["Sales"],
            "secondary_y_columns": [],
            "chart_type": "bar",
            "chart_title": "Top Customers",
        })
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice_json))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["Customer", "Sales"], "rows": [["A", 100], ["B", 200]]}],
                "top customers",
            )
        assert result is not None
        assert result["x_column"] == "Customer"
        assert result["y_columns"] == ["Sales"]
        assert result["chart_type"] == "bar"

    @pytest.mark.asyncio
    async def test_handles_code_fences(self):
        advice_json = '```json\n{"table_index": 0, "x_column": "Month", "y_columns": ["Sales"], "secondary_y_columns": [], "chart_type": "line", "chart_title": "Trend"}\n```'
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice_json))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["Month", "Sales"], "rows": [["Jan", 100], ["Feb", 200]]}],
                "sales trend",
            )
        assert result is not None
        assert result["chart_type"] == "line"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_tables(self):
        result = await get_chart_advice([], "some query")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response("not json"))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_fields(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response('{"table_index": 0}'))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_validates_table_index(self):
        advice = json.dumps({
            "table_index": 5,
            "x_column": "A",
            "y_columns": ["B"],
            "chart_type": "bar",
            "chart_title": "Test",
        })
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["A", "B"], "rows": [["x", 1], ["y", 2]]}],
                "query",
            )
        assert result is not None
        assert result["table_index"] == 0  # Corrected to valid index

    @pytest.mark.asyncio
    async def test_normalizes_string_y_columns(self):
        advice = json.dumps({
            "table_index": 0,
            "x_column": "Name",
            "y_columns": "Amount",
            "chart_type": "bar",
            "chart_title": "Test",
        })
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["Name", "Amount"], "rows": [["A", 100], ["B", 200]]}],
                "query",
            )
        assert result["y_columns"] == ["Amount"]

    @pytest.mark.asyncio
    async def test_passes_chart_suggestion(self):
        advice = json.dumps({
            "table_index": 0,
            "x_column": "Category",
            "y_columns": ["Amount"],
            "chart_type": "pie",
            "chart_title": "Breakdown",
        })
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_response(advice))

        with patch("backend.agents.chart_advisor.anthropic_client", mock_client):
            result = await get_chart_advice(
                [{"headers": ["Category", "Amount"], "rows": [["A", 100], ["B", 200]]}],
                "breakdown",
                chart_suggestion="pie",
            )
        # Verify the suggestion was passed to the API
        call_args = mock_client.messages.create.call_args
        user_content = call_args.kwargs["messages"][0]["content"]
        assert "Suggested chart type: pie" in user_content
