# Code Execution Tool — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add Claude's built-in code execution tool to QueryAgent and AnalysisAgent so computation runs in Anthropic's server-side sandbox instead of LLM mental math.

**Architecture:** Conditionally swap ANALYSIS_TOOLS for code_execution tool in both agents based on `CODE_EXECUTION_ENABLED` config. Parse `STRUCTURED_RESULT:` from code execution stdout to preserve the existing `{headers, rows}` data contract for ChartAgent and Frontend. Kill switch reverts to current behavior.

**Tech Stack:** Python, anthropic SDK 0.84.0+, FastAPI, pytest

**Spec:** `docs/plans/2026-03-13-code-execution-tool-design.md`

---

## Chunk 1: SDK Upgrade + Config + Utils

### Task 1: Upgrade Anthropic SDK

**Files:**
- Modify: `pyproject.toml` (already declares `>=0.84.0`, just need `uv sync`)

- [x] **Step 1: Sync dependencies to install latest SDK**

```bash
uv sync --extra dev --extra langfuse
```

- [x] **Step 2: Verify SDK version and code execution types**

```bash
python -c "import anthropic; print(anthropic.__version__)"
python -c "from anthropic.types import ServerToolUseBlock, CodeExecutionToolResultBlock; print('OK')"
```

Expected: Version >= 0.84.0, types import OK.

- [x] **Step 3: Run existing test suite to catch SDK breaking changes**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short 2>&1 | tail -20
```

Expected: All 820 tests pass. If failures, fix SDK compatibility issues before proceeding.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: sync anthropic SDK to >=0.84.0 for code execution support"
```

---

### Task 2: Add CODE_EXECUTION_ENABLED config

**Files:**
- Modify: `backend/config.py:4-14`
- Test: `tests/unit/test_config_code_exec.py` (new)

- [x] **Step 1: Write failing test**

```python
# tests/unit/test_config_code_exec.py
"""Tests for CODE_EXECUTION_ENABLED config setting."""

import os
from unittest.mock import patch


class TestCodeExecutionConfig:
    def test_default_is_true(self):
        """CODE_EXECUTION_ENABLED defaults to True."""
        from backend.config import Settings
        s = Settings(ANTHROPIC_API_KEY="test")
        assert s.CODE_EXECUTION_ENABLED is True

    def test_can_disable_via_env(self):
        """CODE_EXECUTION_ENABLED can be set to False via env var."""
        with patch.dict(os.environ, {"CODE_EXECUTION_ENABLED": "false"}):
            from backend.config import Settings
            s = Settings(ANTHROPIC_API_KEY="test")
            assert s.CODE_EXECUTION_ENABLED is False
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_config_code_exec.py -v
```

Expected: FAIL — `Settings` has no attribute `CODE_EXECUTION_ENABLED`.

- [x] **Step 3: Add config field**

In `backend/config.py`, add after line 14 (`TALLY_MODE`):

```python
    CODE_EXECUTION_ENABLED: bool = True  # kill switch: False reverts to analysis tools
```

- [x] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_config_code_exec.py -v
```

Expected: 2 passed.

- [x] **Step 5: Run full unit tests to check no regressions**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/ -v --tb=short 2>&1 | tail -5
```

- [x] **Step 6: Commit**

```bash
git add backend/config.py tests/unit/test_config_code_exec.py
git commit -m "feat: add CODE_EXECUTION_ENABLED config setting (default True)"
```

---

### Task 3: Add new utils functions

**Files:**
- Modify: `backend/agents/utils.py:1-29`
- Modify: `tests/unit/test_utils.py:1-68`

- [x] **Step 1: Write failing tests for `find_custom_tool_use_blocks`**

Append to `tests/unit/test_utils.py`:

```python
from backend.agents.utils import find_custom_tool_use_blocks


class TestFindCustomToolUseBlocks:
    def test_returns_only_tool_use_not_server_tool_use(self):
        """Must filter out server_tool_use blocks, keep only tool_use."""
        custom = MagicMock(type="tool_use", name="get_trial_balance")
        server = MagicMock(type="server_tool_use", name="code_execution")
        text = MagicMock(type="text")
        response = MagicMock()
        response.content = [text, custom, server]
        assert find_custom_tool_use_blocks(response) == [custom]

    def test_returns_empty_when_only_server_tool_use(self):
        server = MagicMock(type="server_tool_use")
        code_result = MagicMock(type="code_execution_tool_result")
        response = MagicMock()
        response.content = [server, code_result]
        assert find_custom_tool_use_blocks(response) == []

    def test_returns_all_custom_tool_use_blocks(self):
        b1 = MagicMock(type="tool_use")
        b2 = MagicMock(type="tool_use")
        response = MagicMock()
        response.content = [b1, b2]
        assert find_custom_tool_use_blocks(response) == [b1, b2]
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_utils.py::TestFindCustomToolUseBlocks -v
```

Expected: ImportError — `find_custom_tool_use_blocks` not found.

- [x] **Step 3: Implement `find_custom_tool_use_blocks`**

Add to `backend/agents/utils.py` after `find_all_tool_use_blocks`:

```python
def find_custom_tool_use_blocks(response: Any) -> list[Any]:
    """Find only user-defined tool_use blocks (not server_tool_use).

    Server-managed tools (code_execution) use type="server_tool_use"
    and are resolved inline by the API. This returns only custom tool
    calls that need client-side dispatch.
    """
    return [block for block in response.content if block.type == "tool_use"]
```

- [x] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_utils.py::TestFindCustomToolUseBlocks -v
```

Expected: 3 passed.

- [x] **Step 5: Write failing tests for `extract_code_execution_results`**

Append to `tests/unit/test_utils.py`:

```python
from backend.agents.utils import extract_code_execution_results


class TestExtractCodeExecutionResults:
    def test_extracts_server_tool_use_code(self):
        """Extracts Python code from server_tool_use block."""
        block = MagicMock(type="server_tool_use")
        block.input = {"code": "print(1+1)"}
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert len(results) == 1
        assert results[0] == {"type": "code_written", "code": "print(1+1)"}

    def test_extracts_code_execution_result(self):
        """Extracts stdout/stderr from code_execution_tool_result block."""
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "2\n"
        block.stderr = ""
        block.return_code = 0
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert len(results) == 1
        assert results[0]["type"] == "code_result"
        assert results[0]["stdout"] == "2\n"
        assert results[0]["return_code"] == 0

    def test_handles_pydantic_model_input(self):
        """ServerToolUseBlock.input may be a Pydantic model, not dict."""
        block = MagicMock(type="server_tool_use")
        # Simulate Pydantic model (no .get method)
        block.input = MagicMock(spec=[])
        block.input.code = "x = 42"
        response = MagicMock()
        response.content = [block]
        results = extract_code_execution_results(response)
        assert results[0]["code"] == "x = 42"

    def test_skips_non_code_execution_blocks(self):
        text = MagicMock(type="text")
        tool = MagicMock(type="tool_use")
        response = MagicMock()
        response.content = [text, tool]
        assert extract_code_execution_results(response) == []

    def test_mixed_blocks(self):
        """Multiple code execution blocks in one response."""
        server = MagicMock(type="server_tool_use")
        server.input = {"code": "print('hi')"}
        result = MagicMock(type="code_execution_tool_result")
        result.stdout = "hi\n"
        result.stderr = ""
        result.return_code = 0
        text = MagicMock(type="text")
        response = MagicMock()
        response.content = [text, server, result]
        results = extract_code_execution_results(response)
        assert len(results) == 2
        assert results[0]["type"] == "code_written"
        assert results[1]["type"] == "code_result"
```

- [x] **Step 6: Run tests to verify they fail**

```bash
pytest tests/unit/test_utils.py::TestExtractCodeExecutionResults -v
```

Expected: ImportError — `extract_code_execution_results` not found.

- [x] **Step 7: Implement `extract_code_execution_results`**

Add to `backend/agents/utils.py`:

```python
def extract_code_execution_results(response: Any) -> list[dict[str, Any]]:
    """Extract code execution results from response for logging.

    Returns a list of dicts describing server_tool_use (code written)
    and code_execution_tool_result (stdout/stderr) blocks.
    """
    results: list[dict[str, Any]] = []
    for block in response.content:
        if block.type == "server_tool_use":
            inp = block.input
            code = inp.get("code", "") if isinstance(inp, dict) else getattr(inp, "code", "")
            results.append({"type": "code_written", "code": code})
        elif block.type == "code_execution_tool_result":
            results.append({
                "type": "code_result",
                "stdout": getattr(block, "stdout", ""),
                "stderr": getattr(block, "stderr", ""),
                "return_code": getattr(block, "return_code", None),
            })
    return results
```

Also add `import json` at the top if not present, and update the typing import:

```python
from typing import Any
```

(Already imported — no change needed.)

- [x] **Step 8: Run tests to verify they pass**

```bash
pytest tests/unit/test_utils.py::TestExtractCodeExecutionResults -v
```

Expected: 5 passed.

- [x] **Step 9: Write failing tests for `extract_structured_from_code_execution`**

Append to `tests/unit/test_utils.py`:

```python
from backend.agents.utils import extract_structured_from_code_execution


class TestExtractStructuredFromCodeExecution:
    def test_extracts_structured_result_from_last_line(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'Debug info\nSome calc\nSTRUCTURED_RESULT:{"headers":["Item","Qty"],"rows":[["A",10],["B",20]]}\n'
        response = MagicMock()
        response.content = [block]
        result = extract_structured_from_code_execution(response)
        assert result == {"headers": ["Item", "Qty"], "rows": [["A", 10], ["B", 20]]}

    def test_returns_none_when_no_prefix(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "just some output\n"
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_for_invalid_json(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = "STRUCTURED_RESULT:{bad json\n"
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_when_missing_headers_or_rows(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'STRUCTURED_RESULT:{"only_headers":["A"]}\n'
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None

    def test_returns_none_when_no_code_execution_blocks(self):
        response = MagicMock()
        response.content = [MagicMock(type="text"), MagicMock(type="tool_use")]
        assert extract_structured_from_code_execution(response) is None

    def test_searches_from_last_line_backwards(self):
        """Convention is last line, but search backwards to be robust."""
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = 'STRUCTURED_RESULT:{"headers":["Old"],"rows":[]}\nmore output\nSTRUCTURED_RESULT:{"headers":["New"],"rows":[["x",1]]}\n'
        response = MagicMock()
        response.content = [block]
        result = extract_structured_from_code_execution(response)
        assert result["headers"] == ["New"]

    def test_empty_stdout(self):
        block = MagicMock(type="code_execution_tool_result")
        block.stdout = ""
        response = MagicMock()
        response.content = [block]
        assert extract_structured_from_code_execution(response) is None
```

- [x] **Step 10: Run tests to verify they fail**

```bash
pytest tests/unit/test_utils.py::TestExtractStructuredFromCodeExecution -v
```

Expected: ImportError.

- [x] **Step 11: Implement `extract_structured_from_code_execution`**

Add to `backend/agents/utils.py`:

```python
import json

STRUCTURED_RESULT_PREFIX = "STRUCTURED_RESULT:"


def extract_structured_from_code_execution(response: Any) -> dict[str, Any] | None:
    """Extract {headers, rows} from code_execution stdout if present.

    Looks for a line starting with STRUCTURED_RESULT: followed by JSON.
    Searches from last line backwards (convention: last line of stdout).
    Returns the parsed dict or None if not found/invalid.
    """
    for block in response.content:
        if block.type == "code_execution_tool_result":
            stdout = getattr(block, "stdout", "")
            for line in reversed(stdout.strip().splitlines()):
                if line.startswith(STRUCTURED_RESULT_PREFIX):
                    try:
                        data = json.loads(line[len(STRUCTURED_RESULT_PREFIX):])
                        if isinstance(data, dict) and "headers" in data and "rows" in data:
                            return data
                    except json.JSONDecodeError:
                        pass
    return None
```

- [x] **Step 12: Run tests to verify they pass**

```bash
pytest tests/unit/test_utils.py::TestExtractStructuredFromCodeExecution -v
```

Expected: 7 passed.

- [x] **Step 13: Run all utils tests**

```bash
pytest tests/unit/test_utils.py -v
```

Expected: All tests pass (existing + new).

- [x] **Step 14: Commit**

```bash
git add backend/agents/utils.py tests/unit/test_utils.py
git commit -m "feat: add code execution utils — find_custom_tool_use_blocks, extract helpers"
```

---

## Chunk 2: Prompts (Conditional)

### Task 4: Update QueryAgent prompt

**Files:**
- Modify: `backend/agents/prompts.py:76-168`
- Test: `tests/unit/test_prompts_code_exec.py` (new)

- [x] **Step 1: Write failing tests**

```python
# tests/unit/test_prompts_code_exec.py
"""Tests for code-execution-aware prompt generation."""

from unittest.mock import patch


class TestQueryAgentPromptCodeExec:
    def test_code_exec_enabled_replaces_computation_section(self):
        with patch("backend.config.settings") as mock_settings:
            mock_settings.CODE_EXECUTION_ENABLED = True
            from backend.agents.prompts import build_query_agent_prompt
            prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "## Code Execution" in prompt
        assert "## Computation Tools" not in prompt
        assert "compute_totals" not in prompt
        assert "STRUCTURED_RESULT:" in prompt

    def test_code_exec_disabled_keeps_computation_tools(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=False)
        assert "## Computation Tools" in prompt
        assert "compute_totals" in prompt
        assert "STRUCTURED_RESULT:" not in prompt

    def test_code_exec_enabled_updates_rule_5(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "code_execution tool for ALL calculations" in prompt
        assert "NEVER do mental arithmetic" in prompt

    def test_code_exec_enabled_updates_rule_11(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "code_execution to aggregate" in prompt
        assert "compute_totals with group_by" not in prompt


class TestAnalysisAgentPromptCodeExec:
    def test_code_exec_enabled_replaces_available_tools(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        prompt = build_analysis_agent_prompt("top_n", code_execution_enabled=True)
        assert "## Code Execution" in prompt
        assert "## Available Tools" not in prompt
        assert "sort_by_field" not in prompt
        assert "STRUCTURED_RESULT:" in prompt

    def test_code_exec_disabled_keeps_analysis_tools(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        prompt = build_analysis_agent_prompt("top_n", code_execution_enabled=False)
        assert "## Available Tools" in prompt
        assert "sort_by_field" in prompt

    def test_code_exec_enabled_updates_type_guidance(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        for qt in ("comparison", "trend", "top_n", "aggregation"):
            prompt = build_analysis_agent_prompt(qt, code_execution_enabled=True)
            assert "code_execution" in prompt.lower() or "python" in prompt.lower(), f"Failed for {qt}"
```

- [x] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_prompts_code_exec.py -v
```

Expected: TypeError — `build_query_agent_prompt()` doesn't accept `code_execution_enabled`.

- [x] **Step 3: Update `build_query_agent_prompt`**

Modify `backend/agents/prompts.py:76-168`. Add `code_execution_enabled` parameter with default `False` for backwards compatibility. When `True`, swap the computation section and rules:

```python
def build_query_agent_prompt(current_date: str, code_execution_enabled: bool = False) -> str:
    """Return the system prompt for the query agent.

    Args:
        current_date: Today's date in DD-MM-YYYY format, injected into the prompt.
        code_execution_enabled: When True, replace computation tool references with
            code_execution instructions. When False, keep existing analysis tool refs.
    """
    tally_tool_names = ", ".join(tool["name"] for tool in TALLY_TOOLS)

    if code_execution_enabled:
        computation_section = """\
## Code Execution

You have a code_execution tool that runs Python in a sandbox. Use it for ALL \
calculations — sums, averages, ratios, merges, filtering, sorting. Libraries \
available: pandas, numpy, math, json. NEVER do mental arithmetic."""

        rule_5 = """\
5. **Use code_execution for ALL calculations**: NEVER do mental arithmetic. \
When you need to sum amounts, compute totals, compare values, calculate \
percentages, merge datasets, or any numeric operation, write Python code \
using the code_execution tool. This ensures 100% accuracy for all arithmetic."""

        rule_11 = """\
11. **One-call trend queries**: For trend/time-series queries on VOUCHER data \
(day book, sales register, purchase register), fetch the FULL date range in ONE call, \
then use code_execution to aggregate by month. Do NOT make \
separate API calls per month — the voucher data includes a 'month' field for grouping. \
**IMPORTANT**: get_profit_and_loss and get_balance_sheet return one row per ACCOUNT, \
not per voucher — they CANNOT be grouped by month. For monthly P&L trends, call \
get_profit_and_loss once per month (up to 12 calls for a full year; note: each call \
internally triggers 2 Tally HTTP requests via the subtraction approach, so 12 months ≈ 23 \
HTTP requests). For a lighter alternative, use get_sales_register + \
get_day_book(voucher_type="Purchase") as a proxy for revenue/cost trends (one call each, \
then aggregate by month with code_execution)."""

        structured_output_rule = """\
13. **Structured output**: When your code_execution computes a result table, ALWAYS \
print the final structured data on the LAST line of stdout using this exact prefix:
STRUCTURED_RESULT:{"headers": ["Col1", "Col2"], "rows": [["val1", 123], ["val2", 456]]}
Headers must be strings. Numeric values must be numbers (not strings). You may print \
other text (debug, intermediate steps) before this line — only the STRUCTURED_RESULT \
line is captured for table/chart rendering."""
    else:
        from backend.agents.analysis_agent import ANALYSIS_TOOLS
        analysis_tool_names = ", ".join(tool["name"] for tool in ANALYSIS_TOOLS)

        computation_section = f"""\
## Computation Tools

{analysis_tool_names}"""

        rule_5 = """\
5. **Use computation tools for ALL calculations**: NEVER do mental arithmetic. \
When you need to sum amounts, compute totals, compare values, or calculate \
percentages, ALWAYS use compute_totals, compute_percentage_change, or other \
computation tools. This ensures accuracy."""

        rule_11 = """\
11. **One-call trend queries**: For trend/time-series queries on VOUCHER data \
(day book, sales register, purchase register), fetch the FULL date range in ONE call, \
then use compute_totals with group_by='month' to aggregate by month. Do NOT make \
separate API calls per month — the voucher data includes a 'month' field for grouping. \
**IMPORTANT**: get_profit_and_loss and get_balance_sheet return one row per ACCOUNT, \
not per voucher — they CANNOT be grouped by month. For monthly P&L trends, call \
get_profit_and_loss once per month (up to 12 calls for a full year; note: each call \
internally triggers 2 Tally HTTP requests via the subtraction approach, so 12 months ≈ 23 \
HTTP requests). For a lighter alternative, use get_sales_register + \
get_day_book(voucher_type="Purchase") as a proxy for revenue/cost trends (one call each, \
then group_by='month')."""

        structured_output_rule = ""  # Not needed when using analysis tools

    structured_rule_block = f"\n\n{structured_output_rule}" if structured_output_rule else ""

    return f"""\
You are an accounting data retrieval agent connected to a live TallyPrime instance.
Today's date is {current_date}.
Your job is to fetch the requested data by calling the appropriate Tally tools,
and use computation tools for any calculations.

## Data Fetching Tools

{tally_tool_names}

{computation_section}

## Rules

1. **Date format**: Always use **DD-MM-YYYY** format for all date parameters \
(e.g. 01-04-2025, 31-03-2026).

2. **search_ledger first**: When a user refers to a ledger by a partial or \
informal name, ALWAYS call search_ledger first to find the exact ledger name \
in Tally before using it in other tool calls. Tally requires exact ledger names.

3. **Indian Rupee formatting**: Format all monetary amounts using the Indian \
numbering system with the ₹ symbol (e.g. ₹12,34,567.00). Use two decimal \
places for amounts.

4. **Tally sign convention**:
   - **Negative** amounts = debit / outflow (expenses, assets, payments)
   - **Positive** amounts = credit / inflow (income, liabilities, receipts)
   - This is the standard Tally convention. Do not flip signs.

{rule_5}

6. **Be precise**: Only fetch the data the user asked for. Do not make \
extra tool calls unless necessary.

7. **Error handling**: If a tool call fails, explain the error to the user \
clearly. Do not retry more than once.

8. **Financial year**: The Indian Financial Year runs from April 1 to March 31. \
Interpret "this year", "current FY", "last quarter" etc. relative to today's date.

9. **Date resolution**: For relative expressions like "this month", "last quarter", \
"YTD", "last 3 months", call the `resolve_date_range` tool. \
For specific months (e.g. "April 2025") or financial years (e.g. "FY 2025-26"), \
you can compute the dates directly: \
  - Month: 1st to last day (e.g. April 2025 = 01-04-2025 to 30-04-2025) \
  - FY: April 1 to March 31 (e.g. FY 2025-26 = 01-04-2025 to 31-03-2026) \
  - Quarter: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar \
This saves tool calls. Only use resolve_date_range when unsure.

10. **No markdown tables**: NEVER format data as markdown tables (pipe tables) \
in your response text. The system renders data tables automatically from tool \
results. In your text response, provide a brief summary or analysis of the data \
instead. Example: "Here is the P&L for March 2026. Revenue was ₹X and expenses \
were ₹Y." Do NOT repeat the data in table format.

{rule_11}

12. **Valid voucher_type values for get_day_book**: Use exactly one of: \
"Sales", "Purchase", "Payment", "Receipt", "Journal", "Contra", "Credit Note", \
"Debit Note". The value is case-insensitive (auto-title-cased). Do NOT use plurals \
(e.g. "Payments" is wrong, use "Payment"). Other Tally voucher types exist \
(Delivery Note, Receipt Note, etc.) but are not currently supported by the tool layer.\
{structured_rule_block}
"""
```

- [x] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_prompts_code_exec.py::TestQueryAgentPromptCodeExec -v
```

Expected: 4 passed.

- [x] **Step 5: Update `build_analysis_agent_prompt`**

Modify `backend/agents/prompts.py:171-272`. Add `code_execution_enabled` parameter:

```python
def build_analysis_agent_prompt(query_type: str, code_execution_enabled: bool = False) -> str:
    """Return the system prompt for the analysis agent.

    Args:
        query_type: One of comparison, trend, top_n, aggregation.
        code_execution_enabled: When True, use code_execution instructions
            instead of analysis tool references.
    """
    if code_execution_enabled:
        type_guidance = {
            "comparison": (
                "The user wants to COMPARE values. Write Python code to compute "
                "absolute and percentage changes. Always show both."
            ),
            "trend": (
                "The user wants to see a TREND over time. Write Python code to "
                "calculate period-over-period changes. Identify direction (growing/declining/stable)."
            ),
            "top_n": (
                "The user wants a RANKING. Write Python code to sort and extract "
                "the top or bottom N items. Highlight the #1 item in your summary."
            ),
            "aggregation": (
                "The user wants TOTALS or AVERAGES. Write Python code to compute "
                "totals, optionally grouped. Show grand total and notable sub-totals."
            ),
        }
        specific = type_guidance.get(query_type, "Analyse the data as appropriate for the user's question.")
        tools_section = """\
## Code Execution

You have a code_execution tool that runs Python in a sandbox. Use it for ALL \
calculations. Libraries available: pandas, numpy, math, json. NEVER do mental arithmetic."""

        rule_1 = "1. **Use code_execution for all computation** — write Python code, do not calculate in your head."
        rule_12 = """\
12. **Never manually compute**: NEVER extract or calculate numbers by reading individual \
vouchers/records yourself. Always use code_execution to write Python that computes totals, \
comparisons, and trends. Manual extraction leads to mismatched totals."""

        structured_rule = """
14. **Structured output**: When your code_execution computes a result table, ALWAYS \
print the final structured data on the LAST line of stdout using this exact prefix:
STRUCTURED_RESULT:{"headers": ["Col1", "Col2"], "rows": [["val1", 123], ["val2", 456]]}
Headers must be strings. Numeric values must be numbers (not strings). You may print \
other text before this line — only the STRUCTURED_RESULT line is captured for table/chart rendering."""
    else:
        from backend.agents.analysis_agent import ANALYSIS_TOOLS
        tool_names = ", ".join(tool["name"] for tool in ANALYSIS_TOOLS)

        type_guidance = {
            "comparison": (
                "The user wants to COMPARE values. Use compute_period_comparison or "
                "compute_percentage_change. Always show both absolute and percentage change."
            ),
            "trend": (
                "The user wants to see a TREND over time. Use compute_trend to calculate "
                "period-over-period changes. Identify the direction (growing/declining/stable)."
            ),
            "top_n": (
                "The user wants a RANKING. Use sort_by_field with a limit to get the top or "
                "bottom N items. Highlight the #1 item in your summary."
            ),
            "aggregation": (
                "The user wants TOTALS or AVERAGES. Use compute_totals, optionally with group_by. "
                "Show the grand total and any notable sub-totals."
            ),
        }
        specific = type_guidance.get(query_type, "Analyse the data as appropriate for the user's question.")
        tools_section = f"""\
## Available Tools

{tool_names}"""

        rule_1 = "1. **Use tools for all computation** — do not calculate numbers in your head."
        rule_12 = """\
12. **Never manually compute**: NEVER extract or calculate numbers by reading individual \
vouchers/records yourself. Always use compute_totals (with group_by for breakdowns), \
compute_period_comparison, or compute_trend. If you need per-ledger totals, call \
compute_totals with group_by='ledger_name'. Manual extraction leads to mismatched totals."""
        structured_rule = ""

    structured_block = f"\n\n{structured_rule}" if structured_rule else ""

    return f"""\
You are a financial analysis specialist for Indian businesses using TallyPrime.

You are given raw accounting data fetched from Tally and the user's question.
Use the analysis tools to compute the answer. Do NOT guess numbers — always
use the tools for computation.

## Analysis Focus

{specific}

{tools_section}

## Rules

{rule_1}

2. **Indian Rupee formatting**: Format all monetary amounts using the Indian \
numbering system with the ₹ symbol (e.g. ₹12,34,567.00).

3. **Tally sign convention**:
   - Negative amounts = debit / outflow (expenses, assets, payments)
   - Positive amounts = credit / inflow (income, liabilities, receipts)

4. **Percentages**: Round to 1 decimal place.

5. **For comparisons**: Always show both absolute change AND percentage change.

6. **Output structure**: End your response with:
   - 3-5 bullet-pointed insights (start each with "- ")
   - A line: "Chart suggestion: <type>" where type is one of: \
bar, grouped_bar, line, pie, table_only
   - A line: "Chart title: <descriptive title>" — a short, specific title for the chart \
(e.g. "Monthly Revenue Trend (Apr–Sep 2025)", "Top 5 Customers by Sales", \
"Expenses vs Income: Q1 vs Q2"). Avoid generic titles like "Change % by Period".

7. **Be concise**: Lead with the key finding. Keep the summary to 2-3 sentences.

8. **GST / Tax handling**: Tally vouchers may include GST components (CGST, SGST, IGST).
   - Clearly state whether figures are "base value (excl. GST)" or "invoice value (incl. GST)".
   - If GST treatment changed mid-year, note this and reconcile totals.
   - When a customer total differs between analyses, explain: "₹15.70L base + ₹72K GST = ₹16.42L invoiced".
   - Prefer base values for like-for-like comparisons.

9. **Summary totals**: Always include a "Total" or "Grand Total" row at the bottom of \
comparison and ranking tables. For trend tables, include a "Total" or "Average" row. \
Format: same columns, first column = "Total", numeric columns = sum.

10. **Exact ledger names**: Use ONLY the exact ledger/account names present in the Tally data. \
NEVER create, rename, or infer ledger names from voucher narrations, customer names, or \
other fields. If customer "Amit Jain (Dubai, UAE)" is booked under ledger "SALES EXPORT", \
the ledger name is "SALES EXPORT" — do NOT fabricate "SALES EXPORT (Dubai)".

11. **Chart title must match data**: The "Chart title:" line must accurately describe \
the data being charted. If the data contains only sales figures, do NOT title it \
"Gross Profit & Net Profit Comparison". Title should reflect the actual columns/metrics \
in the structured data (e.g. "Q2 vs Q3: Sales by Ledger").

{rule_12}

13. **Explain data gaps**: If trend data starts mid-FY (e.g. Jul instead of Apr) or has \
months with no transactions, explicitly state this. Example: "No sales transactions were \
recorded for Apr-Jun 2025, so the trend starts from Jul 2025." Do not silently omit months.\
{structured_block}
"""
```

- [x] **Step 6: Run analysis prompt tests**

```bash
pytest tests/unit/test_prompts_code_exec.py::TestAnalysisAgentPromptCodeExec -v
```

Expected: 3 passed.

- [x] **Step 7: Run all prompt tests + existing prompt tests**

```bash
pytest tests/unit/test_prompts_code_exec.py -v
ANTHROPIC_API_KEY=test-key pytest tests/unit/ -v --tb=short -q 2>&1 | tail -5
```

Expected: All pass. Existing tests use the default `code_execution_enabled=False` so no breakage.

- [x] **Step 8: Commit**

```bash
git add backend/agents/prompts.py tests/unit/test_prompts_code_exec.py
git commit -m "feat: conditional prompts for code execution — query and analysis agents"
```

---

## Chunk 3: QueryAgent + Orchestrator Changes

### Task 5: Update QueryAgent tool loop

**Files:**
- Modify: `backend/agents/query_agent.py:1-196`
- Test: `tests/unit/test_query_agent.py` (append)

- [x] **Step 1: Write failing test for code execution tool list**

Append to `tests/unit/test_query_agent.py`:

```python
class TestQueryAgentCodeExecution:
    @pytest.mark.asyncio
    async def test_code_exec_enabled_uses_code_execution_tool(self):
        """When CODE_EXECUTION_ENABLED=True, tool list includes code_execution, excludes analysis tools."""
        from backend.agents.query_agent import QueryAgent, _build_query_tools
        from backend.agents.tools import TALLY_TOOLS, DATE_TOOLS

        tools = _build_query_tools(code_execution_enabled=True)
        tool_names = [t.get("name", "") for t in tools if isinstance(t, dict) and "name" in t]
        tool_types = [t.get("type", "") for t in tools if isinstance(t, dict) and "type" in t]
        # Should have Tally tools + date tools
        assert "get_trial_balance" in tool_names
        assert "resolve_date_range" in tool_names
        # Should NOT have analysis tools
        assert "compute_totals" not in tool_names
        assert "sort_by_field" not in tool_names
        # Should have code_execution
        assert "code_execution_20260120" in tool_types

    @pytest.mark.asyncio
    async def test_code_exec_disabled_uses_analysis_tools(self):
        """When CODE_EXECUTION_ENABLED=False, tool list includes analysis tools, excludes code_execution."""
        from backend.agents.query_agent import _build_query_tools

        tools = _build_query_tools(code_execution_enabled=False)
        tool_names = [t["name"] for t in tools if "name" in t]
        tool_types = [t.get("type", "") for t in tools]
        assert "compute_totals" in tool_names
        assert "code_execution_20260120" not in tool_types
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_query_agent.py::TestQueryAgentCodeExecution -v
```

Expected: ImportError — `_build_query_tools` not found.

- [x] **Step 3: Implement QueryAgent changes**

Modify `backend/agents/query_agent.py`. Key changes:

1. Add `_build_query_tools` function
2. Import new utils
3. Update the tool loop to use `find_custom_tool_use_blocks` when code execution enabled
4. Add structured output capture
5. Add code execution logging
6. Conditional message history append

Replace the module-level tool list and update the agent class:

```python
# At top, add imports:
from backend.agents.utils import (
    extract_text,
    find_all_tool_use_blocks,
    find_custom_tool_use_blocks,
    extract_code_execution_results,
    extract_structured_from_code_execution,
)

# Replace line 38 (_ALL_QUERY_TOOLS) with:
CODE_EXECUTION_TOOL = {"type": "code_execution_20260120"}


def _build_query_tools(code_execution_enabled: bool) -> list:
    """Build tool list based on code execution config."""
    if code_execution_enabled:
        return TALLY_TOOLS + DATE_TOOLS + [CODE_EXECUTION_TOOL]
    return TALLY_TOOLS + ANALYSIS_TOOLS + DATE_TOOLS
```

In `QueryAgent.execute`, update:

```python
# Line 79: pass code_execution_enabled to prompt
system_prompt = build_query_agent_prompt(current_date, code_execution_enabled=settings.CODE_EXECUTION_ENABLED)

# Line 100: use dynamic tool list
tools=_build_query_tools(settings.CODE_EXECUTION_ENABLED),

# After line 118 (text logging), add code execution logging:
if settings.CODE_EXECUTION_ENABLED:
    for cer in extract_code_execution_results(response):
        if cer["type"] == "code_written":
            logger.info("QueryAgent turn %d — code_execution code:\n%s", turn, cer["code"])
        elif cer["type"] == "code_result":
            logger.info("QueryAgent turn %d — code_execution stdout:\n%s", turn, cer["stdout"])
            if cer.get("stderr"):
                logger.warning("QueryAgent turn %d — code_execution stderr:\n%s", turn, cer["stderr"])

# Line 130: use find_custom_tool_use_blocks when code execution enabled
if settings.CODE_EXECUTION_ENABLED:
    tool_blocks = find_custom_tool_use_blocks(response)
else:
    tool_blocks = find_all_tool_use_blocks(response)

# After tool dispatch loop (after line 167), capture structured output:
if settings.CODE_EXECUTION_ENABLED:
    structured = extract_structured_from_code_execution(response)
    if structured:
        tool_results.append({
            "tool_name": "code_execution",
            "tool_input": {},
            "result": {"success": True, "data": structured},
        })

# Lines 174-180: conditional message history append
messages.append({"role": "assistant", "content": response.content})
if tool_result_entries:
    messages.append({"role": "user", "content": tool_result_entries})
```

- [x] **Step 4: Run new tests**

```bash
pytest tests/unit/test_query_agent.py::TestQueryAgentCodeExecution -v
```

Expected: 2 passed.

- [x] **Step 5: Write test for code execution response handling in tool loop**

Append to `tests/unit/test_query_agent.py`:

```python
    @pytest.mark.asyncio
    async def test_code_exec_response_captures_structured_output(self):
        """When response has code_execution_tool_result with STRUCTURED_RESULT, capture it."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        # Turn 1: tool_use for get_stock_summary
        tool_response = _make_tool_call_response("get_stock_summary", {"as_on_date": "13-03-2026"})
        # Turn 2: end_turn with code execution results (server-resolved inline)
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        text_block = MagicMock(type="text", text="Stock analysis complete.")
        server_tool = MagicMock(type="server_tool_use")
        server_tool.input = {"code": "print('hello')"}
        code_result = MagicMock(type="code_execution_tool_result")
        code_result.stdout = 'STRUCTURED_RESULT:{"headers":["Item","Days"],"rows":[["A",100]]}\n'
        code_result.stderr = ""
        code_result.return_code = 0
        final_response.content = [text_block, server_tool, code_result]

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
            patch("backend.agents.query_agent.settings") as mock_settings,
        ):
            mock_settings.CLAUDE_MODEL = "test-model"
            mock_settings.CODE_EXECUTION_ENABLED = True
            mock_claude.messages.create = AsyncMock(side_effect=[tool_response, final_response])
            mock_exec.return_value = {"success": True, "data": [{"name": "Item A", "qty": 10}]}

            agent = QueryAgent()
            result = await agent.execute("stock analysis", mock_client, session)

        assert result["message"] == "Stock analysis complete."
        # Should have captured structured output as synthetic tool result
        code_exec_results = [r for r in result["tool_results"] if r["tool_name"] == "code_execution"]
        assert len(code_exec_results) == 1
        assert code_exec_results[0]["result"]["data"]["headers"] == ["Item", "Days"]
```

- [x] **Step 6: Run test**

```bash
pytest tests/unit/test_query_agent.py::TestQueryAgentCodeExecution::test_code_exec_response_captures_structured_output -v
```

Expected: PASS (implementation from step 3 should handle this).

- [x] **Step 7: Run all query agent tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/test_query_agent.py -v
```

Expected: All pass (existing + new).

- [x] **Step 8: Commit**

```bash
git add backend/agents/query_agent.py tests/unit/test_query_agent.py
git commit -m "feat: add code execution support to QueryAgent tool loop"
```

---

### Task 6: Update Orchestrator

**Files:**
- Modify: `backend/agents/orchestrator.py:246-249`

- [x] **Step 1: Add `"code_execution"` to `_COMPUTED_TOOL_NAMES`**

In `backend/agents/orchestrator.py`, change line 246-249:

```python
_COMPUTED_TOOL_NAMES = {
    "compute_totals", "compute_trend", "compute_period_comparison",
    "compute_percentage_change", "sort_by_field",
    "code_execution",
}
```

- [x] **Step 2: Run existing orchestrator tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/test_orchestrator.py -v
```

Expected: All pass.

- [x] **Step 3: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat: add code_execution to computed tool names in orchestrator"
```

---

## Chunk 4: AnalysisAgent Changes

### Task 7: Update AnalysisAgent tool loop

**Files:**
- Modify: `backend/agents/analysis_agent.py:380-567`
- Test: `tests/unit/test_analysis_agent.py` (append)

- [x] **Step 1: Write failing test for code execution tool list**

Append to `tests/unit/test_analysis_agent.py`:

```python
class TestAnalysisAgentCodeExecution:
    def test_build_analysis_tools_code_exec_enabled(self):
        from backend.agents.analysis_agent import _build_analysis_tools
        tools = _build_analysis_tools(code_execution_enabled=True)
        tool_types = [t.get("type", "") for t in tools]
        assert "code_execution_20260120" in tool_types
        # Should not contain named analysis tools
        tool_names = [t.get("name", "") for t in tools if "name" in t]
        assert "compute_totals" not in tool_names

    def test_build_analysis_tools_code_exec_disabled(self):
        from backend.agents.analysis_agent import _build_analysis_tools
        tools = _build_analysis_tools(code_execution_enabled=False)
        tool_names = [t["name"] for t in tools]
        assert "compute_totals" in tool_names
```

- [x] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_analysis_agent.py::TestAnalysisAgentCodeExecution -v
```

Expected: ImportError — `_build_analysis_tools` not found.

- [x] **Step 3: Implement AnalysisAgent changes**

Add to `backend/agents/analysis_agent.py`:

```python
# After ANALYSIS_TOOLS definition and before handlers, add:
CODE_EXECUTION_TOOL = {"type": "code_execution_20260120"}


def _build_analysis_tools(code_execution_enabled: bool) -> list:
    """Build tool list based on code execution config."""
    if code_execution_enabled:
        return [CODE_EXECUTION_TOOL]
    return ANALYSIS_TOOLS
```

Add imports at top:

```python
from backend.agents.utils import (
    extract_text,
    find_all_tool_use_blocks,
    find_custom_tool_use_blocks,
    extract_code_execution_results,
    extract_structured_from_code_execution,
)
from backend.config import settings
```

Update `AnalysisAgent.execute`:

```python
# Line 416: pass code_execution_enabled to prompt
system_prompt = build_analysis_agent_prompt(query_type, code_execution_enabled=settings.CODE_EXECUTION_ENABLED)

# Line 457: use dynamic tool list
tools=_build_analysis_tools(settings.CODE_EXECUTION_ENABLED),

# After line 483 (text logging), add code execution logging:
if settings.CODE_EXECUTION_ENABLED:
    for cer in extract_code_execution_results(response):
        if cer["type"] == "code_written":
            logger.info("AnalysisAgent turn %d — code_execution code:\n%s", turn, cer["code"])
        elif cer["type"] == "code_result":
            logger.info("AnalysisAgent turn %d — code_execution stdout:\n%s", turn, cer["stdout"])
            if cer.get("stderr"):
                logger.warning("AnalysisAgent turn %d — code_execution stderr:\n%s", turn, cer["stderr"])

# After line 483 and before the stop_reason check, capture structured data:
if settings.CODE_EXECUTION_ENABLED:
    structured = extract_structured_from_code_execution(response)
    if structured and "headers" in structured and "rows" in structured:
        last_table_data = {"headers": structured["headers"], "rows": structured["rows"]}
        if query_type == "top_n":
            ranked_table_data = last_table_data
        elif query_type == "trend":
            trend_table_data = last_table_data
        elif query_type == "comparison":
            comparison_table_data = last_table_data

# Line 502: use find_custom_tool_use_blocks when code execution enabled
if settings.CODE_EXECUTION_ENABLED:
    tool_blocks = find_custom_tool_use_blocks(response)
else:
    tool_blocks = find_all_tool_use_blocks(response)

# Lines 546-550: conditional message history append
messages.append({"role": "assistant", "content": response.content})
if tool_result_entries:
    messages.append({"role": "user", "content": tool_result_entries})
```

- [x] **Step 4: Run new tests**

```bash
pytest tests/unit/test_analysis_agent.py::TestAnalysisAgentCodeExecution -v
```

Expected: 2 passed.

- [x] **Step 5: Write test for structured output capture in AnalysisAgent**

Append to `tests/unit/test_analysis_agent.py`:

```python
    @pytest.mark.asyncio
    async def test_code_exec_captures_structured_table_data(self):
        """AnalysisAgent captures STRUCTURED_RESULT from code execution as table data."""
        # Response with code execution results (end_turn, no custom tool calls)
        response = MagicMock()
        response.stop_reason = "end_turn"
        text_block = MagicMock(type="text")
        text_block.text = "Top 5 items by sales.\n- Item A leads\nChart suggestion: bar\nChart title: Top Items"
        server_tool = MagicMock(type="server_tool_use")
        server_tool.input = {"code": "import json; print(json.dumps({'headers':['Item','Sales'],'rows':[['A',100]]}))"}
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
            mock_claude.messages.create = AsyncMock(return_value=response)

            agent = AnalysisAgent()
            result = await agent.execute(
                raw_data=[{"item": "A", "amount": 100}],
                computed_data=None,
                user_query="top 5 items",
                query_type="top_n",
            )

        assert result["data"]["headers"] == ["Item", "Sales"]
        assert result["data"]["rows"][0] == ["A", 100]
```

- [x] **Step 6: Run test**

```bash
pytest tests/unit/test_analysis_agent.py::TestAnalysisAgentCodeExecution::test_code_exec_captures_structured_table_data -v
```

Expected: PASS.

- [x] **Step 7: Run all analysis agent tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/test_analysis_agent.py -v
```

Expected: All pass (existing + new).

- [x] **Step 8: Commit**

```bash
git add backend/agents/analysis_agent.py tests/unit/test_analysis_agent.py
git commit -m "feat: add code execution support to AnalysisAgent tool loop"
```

---

## Chunk 5: Integration Verification + Final Tests

### Task 8: Full test suite verification

**Files:** None (verification only)

- [x] **Step 1: Run full backend tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short 2>&1 | tail -20
```

Expected: All existing + new tests pass.

- [x] **Step 2: Run with CODE_EXECUTION_ENABLED=False (kill switch)**

```bash
CODE_EXECUTION_ENABLED=false ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short 2>&1 | tail -20
```

Expected: All pass — identical behavior to before the changes.

- [x] **Step 3: Run frontend tests (should be unaffected)**

```bash
cd frontend && npm test 2>&1 | tail -5
```

Expected: 111 tests pass.

- [x] **Step 4: Verify the server starts**

```bash
timeout 5 uvicorn backend.main:app --host 0.0.0.0 --port 8000 2>&1 || true
```

Expected: Server starts without import errors.

---

### Task 9: Update spec status and commit

**Files:**
- Modify: `docs/plans/2026-03-13-code-execution-tool-design.md:3`

- [x] **Step 1: Mark spec as implemented**

Change line 3 from `**Status**: Draft` to `**Status**: Implemented`.

- [x] **Step 2: Final commit**

```bash
git add docs/plans/2026-03-13-code-execution-tool-design.md
git commit -m "docs: mark code execution tool design as implemented"
```

---

## Post-Implementation Notes

**Status**: All 9 tasks COMPLETE. 13 commits (d5bcfbe..839e064).

### Additional work beyond plan:
- **Code review fixes** (commit 17de8d2): Guarded empty tool_result_entries in QueryAgent, fixed STRUCTURED_RESULT prompt format to match parser expectations
- **Eval optimization**: Deleted mock_tally_validation (redundant), trimmed edge_case_gauntlet (8→6), trends_and_breakdowns (7→6), edge_case_gauntlet_mock (8→6), trends_and_breakdowns_mock (7→6)
- **New eval scenario**: code_execution_validation.yaml (5 turns, computation-heavy) + code_execution_validation_mock.yaml (5 turns, includes stock reorder)
- **e2e_live trimmed**: 19→12 tests (removed 7 covered by eval scenarios)

### Post-Implementation Bugs Found & Fixed

**Commit 56cbba9** — Fix code_execution tool format + pydantic upgrade:
1. **Missing `name` field**: CODE_EXECUTION_TOOL dict in both query_agent.py and analysis_agent.py lacked `name: "code_execution"` — API rejected the tool definition
2. **Pydantic serialization crash**: `by_alias: NoneType` error when anthropic SDK 0.84.0 tried to serialize models. Fixed by upgrading pydantic 2.10.6 → 2.12.5
3. **AnalysisAgent truncation**: max_tokens 4096 insufficient with code_execution overhead (sandbox output inflates response). Increased to 16384

**Commit 839e064** — QueryAgent data-fetch only + chart pipeline fix:
4. **Architecture change (Option C1)**: Removed code_execution and analysis tools from QueryAgent entirely. QueryAgent is now data-fetch only (TALLY_TOOLS + DATE_TOOLS). AnalysisAgent is sole computation authority for ALL query types. Orchestrator routes all queries with data to AnalysisAgent.
5. **STRUCTURED_RESULT not reaching ChartAgent**: Added `_extract_structured_from_text()` fallback to parse STRUCTURED_RESULT from assistant text when code_execution stdout doesn't contain it. Also strips STRUCTURED_RESULT prefix from user-facing messages.
6. **Robust STRUCTURED_RESULT parsing**: `extract_structured_from_code_execution()` now searches ALL stdout lines (not just reversed), adds warning logs on parse failures
7. **Classifier over-routing to clarification_needed**: Added data-availability rule to classifier prompt — assume data exists in Tally, only use clarification_needed for genuinely ambiguous queries
8. **Eval timeout**: Increased 120s → 180s to accommodate code_execution latency

### Eval Results (run_20260313_205515, mock mode)
- manual_test_regression_mock: 5/5 turns, all tables rendered, avg factual=4.6, quality=5.0, coherence=5.0
- code_execution_validation_mock: 5/5 turns, 3 tables, turn 3 timeout (180s), turn 5 clarification instead of computation

### Test counts:
- Backend: 699 (unit + integration + e2e) — removed 1 QueryAgent code_exec test
- Frontend: 111 Vitest + 39 Playwright
- e2e_live: 12 (gated by RUN_LIVE_TESTS=1)
- Eval: 13 scenarios (8 base + 5 mock), 78 turns
