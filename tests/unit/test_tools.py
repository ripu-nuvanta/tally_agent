"""Unit tests for backend/agents/tools.py — tool schemas and handler mapping."""

import asyncio
import inspect

import pytest

from backend.agents.tools import TALLY_TOOLS, TOOL_HANDLERS, execute_tool, DATE_TOOLS, execute_date_tool


# ---------------------------------------------------------------------------
# Expected tool catalogue
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES = [
    "get_trial_balance",
    "get_profit_and_loss",
    "get_balance_sheet",
    "get_ledger_transactions",
    "get_day_book",
    "get_outstanding_receivables",
    "get_outstanding_payables",
    "get_stock_summary",
    "get_sales_register",
    "get_purchase_register",
    "search_ledger",
    "list_companies",
]

# Tools that use from_date + to_date
DATE_RANGE_TOOLS = [
    "get_trial_balance",
    "get_profit_and_loss",
    "get_ledger_transactions",
    "get_day_book",
    "get_sales_register",
    "get_purchase_register",
]

# Tools that use as_on_date
AS_ON_DATE_TOOLS = [
    "get_balance_sheet",
    "get_outstanding_receivables",
    "get_outstanding_payables",
    "get_stock_summary",
]


def _tool_by_name(name: str) -> dict:
    """Helper to find a tool schema by name."""
    for t in TALLY_TOOLS:
        if t["name"] == name:
            return t
    raise KeyError(f"Tool {name!r} not found in TALLY_TOOLS")


# ---------------------------------------------------------------------------
# TestToolSchemas
# ---------------------------------------------------------------------------


class TestToolSchemas:
    """Validate the TALLY_TOOLS list matches Claude tool-calling format."""

    def test_all_tools_have_required_fields(self):
        """Every tool must have name, description, and input_schema with type=object."""
        for tool in TALLY_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"
            schema = tool["input_schema"]
            assert schema.get("type") == "object", (
                f"Tool {tool['name']} input_schema.type must be 'object'"
            )
            assert "properties" in schema, (
                f"Tool {tool['name']} input_schema missing 'properties'"
            )

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in TALLY_TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names detected"

    def test_expected_tools_exist(self):
        """All 12 expected tool names must be present."""
        actual_names = {t["name"] for t in TALLY_TOOLS}
        for name in EXPECTED_TOOL_NAMES:
            assert name in actual_names, f"Expected tool {name!r} not found"
        assert len(TALLY_TOOLS) == 12

    def test_date_tools_require_dates(self):
        """Date-range tools must require from_date and to_date."""
        for name in DATE_RANGE_TOOLS:
            tool = _tool_by_name(name)
            schema = tool["input_schema"]
            required = schema.get("required", [])
            assert "from_date" in required, f"{name} must require from_date"
            assert "to_date" in required, f"{name} must require to_date"

    def test_as_on_date_tools(self):
        """Point-in-time tools must require as_on_date."""
        for name in AS_ON_DATE_TOOLS:
            tool = _tool_by_name(name)
            schema = tool["input_schema"]
            required = schema.get("required", [])
            assert "as_on_date" in required, f"{name} must require as_on_date"

    def test_ledger_transactions_requires_ledger_name(self):
        tool = _tool_by_name("get_ledger_transactions")
        required = tool["input_schema"].get("required", [])
        assert "ledger_name" in required

    def test_search_ledger_requires_search_term(self):
        tool = _tool_by_name("search_ledger")
        required = tool["input_schema"].get("required", [])
        assert "search_term" in required

    def test_list_companies_has_no_required_params(self):
        tool = _tool_by_name("list_companies")
        required = tool["input_schema"].get("required", [])
        assert required == [] or required is None or len(required) == 0

    def test_day_book_has_optional_voucher_type(self):
        tool = _tool_by_name("get_day_book")
        props = tool["input_schema"]["properties"]
        assert "voucher_type" in props
        required = tool["input_schema"].get("required", [])
        assert "voucher_type" not in required

    def test_stock_summary_has_optional_stock_group(self):
        tool = _tool_by_name("get_stock_summary")
        props = tool["input_schema"]["properties"]
        assert "stock_group" in props
        required = tool["input_schema"].get("required", [])
        assert "stock_group" not in required

    def test_descriptions_are_non_empty(self):
        for tool in TALLY_TOOLS:
            assert len(tool["description"]) > 10, (
                f"Tool {tool['name']} description too short"
            )


# ---------------------------------------------------------------------------
# TestToolHandlers
# ---------------------------------------------------------------------------


class TestToolHandlers:
    """Validate TOOL_HANDLERS dict matches TALLY_TOOLS."""

    def test_every_tool_has_handler(self):
        """Every tool in TALLY_TOOLS must have a corresponding handler."""
        tool_names = {t["name"] for t in TALLY_TOOLS}
        handler_names = set(TOOL_HANDLERS.keys())
        assert tool_names == handler_names, (
            f"Mismatch — missing handlers: {tool_names - handler_names}, "
            f"extra handlers: {handler_names - tool_names}"
        )

    def test_handlers_are_callable(self):
        for name, handler in TOOL_HANDLERS.items():
            assert callable(handler), f"Handler for {name!r} is not callable"

    def test_handlers_are_async(self):
        """All handlers must be async functions (coroutine functions)."""
        for name, handler in TOOL_HANDLERS.items():
            assert inspect.iscoroutinefunction(handler), (
                f"Handler for {name!r} must be async"
            )


# ---------------------------------------------------------------------------
# TestExecuteTool
# ---------------------------------------------------------------------------


class TestExecuteTool:
    """Test the execute_tool entry point with mocked client."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await execute_tool(None, "nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_connection_error_returns_error(self):
        """TallyConnectionError should be caught and returned as error dict."""
        from unittest.mock import AsyncMock, patch
        from backend.tally_bridge.exceptions import TallyConnectionError

        mock_client = AsyncMock()
        with patch.dict(
            TOOL_HANDLERS,
            {"list_companies": AsyncMock(side_effect=TallyConnectionError("offline"))},
        ):
            result = await execute_tool(mock_client, "list_companies", {})
        assert "error" in result
        assert "offline" in result["error"]

    @pytest.mark.asyncio
    async def test_response_error_returns_error(self):
        from unittest.mock import AsyncMock, patch
        from backend.tally_bridge.exceptions import TallyResponseError

        mock_client = AsyncMock()
        with patch.dict(
            TOOL_HANDLERS,
            {"list_companies": AsyncMock(side_effect=TallyResponseError("bad xml"))},
        ):
            result = await execute_tool(mock_client, "list_companies", {})
        assert "error" in result
        assert "bad xml" in result["error"]

    @pytest.mark.asyncio
    async def test_success_returns_data(self):
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock()
        with patch.dict(
            TOOL_HANDLERS,
            {"list_companies": AsyncMock(return_value=[{"name": "Acme"}])},
        ):
            result = await execute_tool(mock_client, "list_companies", {})
        assert result == {"success": True, "data": [{"name": "Acme"}]}

    @pytest.mark.asyncio
    async def test_unexpected_error_logs_exception(self):
        """Issue #7: Unexpected exceptions must be logged before returning error."""
        from unittest.mock import AsyncMock, patch

        mock_client = AsyncMock()
        with patch.dict(
            TOOL_HANDLERS,
            {"list_companies": AsyncMock(side_effect=RuntimeError("boom"))},
        ):
            with patch("backend.agents.tools.logger") as mock_logger:
                result = await execute_tool(mock_client, "list_companies", {})

                mock_logger.exception.assert_called_once()

        assert "error" in result
        assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# TestDateToolExecution
# ---------------------------------------------------------------------------


class TestDateToolExecution:
    """Test the execute_date_tool entry point."""

    def test_resolve_date_range_q2(self):
        result = execute_date_tool("resolve_date_range", {"description": "Q2"})
        assert result["success"] is True
        assert "from_date" in result["data"]

    def test_unknown_date_tool(self):
        result = execute_date_tool("unknown_tool", {})
        assert "error" in result
