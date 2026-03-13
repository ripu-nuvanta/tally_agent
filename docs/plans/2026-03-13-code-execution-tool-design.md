# Code Execution Tool Integration — Design Spec

**Date**: 2026-03-13
**Status**: Implemented
**Motivation**: LLM does mental arithmetic on fetched Tally data and gets it wrong (e.g. stock coverage: 12 units / 2.2 avg monthly sales = "55 days" instead of ~164 days). Moving all computation to Claude's server-side code execution sandbox eliminates this class of errors.

## Problem

The query agent fetches data from Tally via tools (get_stock_summary, get_sales_register, etc.) and has access to analysis tools (compute_totals, sort_by_field, etc.). However:

1. **Analysis tools are too narrow** — they handle aggregation and sorting but not per-row derived calculations (ratios, coverage days, margins).
2. **The LLM fills the gap with mental math** — it manually computes divisions, multiplications, and comparisons in its text output. This is unreliable, especially with 10+ items.
3. **Dataset merging is done mentally** — when two tool results need to be joined (e.g. stock quantities + sales quantities), the LLM does this in its head, compounding errors.

## Solution

Integrate Claude's built-in **Code Execution Tool** (`code_execution_20260120`), which runs Python in Anthropic's server-side sandbox. The LLM writes Python code (which it's good at) instead of doing arithmetic (which it's bad at). Results are deterministic.

## Scope

### In Scope
- Add code execution tool to QueryAgent and AnalysisAgent
- SDK upgrade (anthropic 0.49.0 → 0.84.0+)
- Config kill switch (`CODE_EXECUTION_ENABLED`)
- Handle new response block types (`server_tool_use`, `code_execution_tool_result`)
- Update system prompts (both agents) to prefer code execution, conditionally based on kill switch
- Logging for observability
- Unit tests for new block type handling

### Out of Scope
- Removing existing analysis tools code (kept intact, just hidden from tool list)
- Programmatic tool calling (Claude calling Tally tools from within sandbox)
- Container persistence across sessions
- Frontend changes (code execution is transparent to the frontend)

## Technical Design

### 1. SDK Upgrade

Upgrade `anthropic` from 0.49.0 to 0.84.0+. The new SDK provides:
- `ServerToolUseBlock` type (for code Claude wants to execute)
- `CodeExecutionToolResultBlock` type (sandbox results with stdout/stderr)
- Support for `{"type": "code_execution_20260120"}` in tools array

**Verification steps** (before any other code changes):
1. Run `uv sync --extra dev --extra langfuse` after bumping version
2. Confirm: `python -c "from anthropic.types import ServerToolUseBlock; print('OK')"`
3. Run full existing test suite (820 tests) — expect all pass
4. Review SDK changelog for breaking changes in response object structure, error types, client init

**Note**: `pyproject.toml` may already declare a version constraint. Verify it matches and that `uv.lock` is regenerated.

### 2. Config

```python
# backend/config.py — new field
CODE_EXECUTION_ENABLED: bool = True  # kill switch to revert to analysis tools
```

### 3. Tool List Assembly

The code execution tool schema uses `type` only — no `name` field:
```python
CODE_EXECUTION_TOOL = {"type": "code_execution_20260120"}
```

**Important**: Verify this format against the SDK/API docs during implementation. If the API requires or accepts a `name` field, add it. If it rejects it, omit it. The SDK may provide a helper type (e.g. `CodeExecutionToolParam`) — prefer that over raw dicts.

**QueryAgent** (`query_agent.py`):
```python
# Build tool list based on config
if settings.CODE_EXECUTION_ENABLED:
    _ALL_QUERY_TOOLS = TALLY_TOOLS + DATE_TOOLS + [CODE_EXECUTION_TOOL]
else:
    _ALL_QUERY_TOOLS = TALLY_TOOLS + ANALYSIS_TOOLS + DATE_TOOLS  # current behavior
```

**AnalysisAgent** (`analysis_agent.py`):
```python
if settings.CODE_EXECUTION_ENABLED:
    _AGENT_TOOLS = [CODE_EXECUTION_TOOL]
else:
    _AGENT_TOOLS = ANALYSIS_TOOLS  # current behavior
```

### 4. Tool Loop Changes

Both agents share the same pattern. The key changes in the `while True` loop:

#### a) Block type filtering

```python
# New helper in utils.py
def find_custom_tool_use_blocks(response) -> list:
    """Find only user-defined tool_use blocks (not server_tool_use)."""
    return [b for b in response.content if b.type == "tool_use"]
```

#### b) Stop condition

```python
# Current:
if response.stop_reason != "tool_use":
    # final answer

# New — unchanged. When code_execution is used, the API runs it server-side
# and returns results inline. If Claude also needs custom tools, stop_reason
# is "tool_use" and we'll find custom tool_use blocks. If no custom tools
# are needed, stop_reason is "end_turn" and we extract the final text.
```

The stop condition logic doesn't actually change because:
- `server_tool_use` + `code_execution_tool_result` are resolved inline by the API
- `stop_reason = "tool_use"` only occurs when there are custom `tool_use` blocks
- We already check `stop_reason != "tool_use"` which handles both cases correctly

#### c) Tool dispatch

```python
tool_blocks = find_custom_tool_use_blocks(response)  # excludes server_tool_use

if not tool_blocks and response.stop_reason != "end_turn":
    # Edge case: stop_reason might be something unexpected
    # Treat as final answer
    ...

for tool_block in tool_blocks:
    # Existing dispatch logic — unchanged
    if tool_block.name in _ANALYSIS_TOOL_NAMES:
        result = execute_analysis_tool(...)
    elif tool_block.name in _DATE_TOOL_NAMES:
        result = execute_date_tool(...)
    else:
        result = await execute_tool(client, ...)
```

#### d) Message history

```python
# Append assistant's response (includes server_tool_use + code_execution_tool_result + text + tool_use)
messages.append({"role": "assistant", "content": response.content})

# Only append tool_result entries for CUSTOM tool calls
# server_tool_use results are already in the assistant message
if tool_result_entries:
    messages.append({"role": "user", "content": tool_result_entries})
```

### 5. Utils Changes

```python
# backend/agents/utils.py

def find_custom_tool_use_blocks(response) -> list:
    """Find only user-defined tool_use blocks (not server_tool_use)."""
    return [b for b in response.content if b.type == "tool_use"]

def extract_code_execution_results(response) -> list[dict]:
    """Extract code execution results from response for logging."""
    results = []
    for block in response.content:
        if block.type == "server_tool_use":
            # ServerToolUseBlock.input may be a dict or Pydantic model — use getattr for safety
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

**Notes**:
- `extract_text` is unchanged — it already only looks at `type == "text"` blocks.
- `find_tool_use_block` (singular) is also safe — it filters on `type == "tool_use"` which won't match `server_tool_use`.
- When `CODE_EXECUTION_ENABLED = False`, both agents use `find_all_tool_use_blocks` (unchanged behavior). When `True`, use `find_custom_tool_use_blocks`.

### 6. Prompt Changes

Both prompts must be **conditional on `CODE_EXECUTION_ENABLED`** to avoid mismatch between prompt text and actual tool list.

**QueryAgent prompt** (`build_query_agent_prompt`):

The current prompt hardcodes `analysis_tool_names` in two places:
- "## Computation Tools" section (line 100-102)
- Rule 5 references specific tool names

When `CODE_EXECUTION_ENABLED = True`:
- Replace "## Computation Tools" section with "## Code Execution" section
- Tool names list: only Tally tools + resolve_date_range (no analysis tool names)
- Rule 5 becomes:
  > Use the code_execution tool for ALL calculations: NEVER do mental arithmetic. When you need to sum amounts, compute totals, compare values, calculate percentages, merge datasets, or any numeric operation, write Python code using the code_execution tool. Libraries available: pandas, numpy, math, json. This ensures 100% accuracy for all arithmetic.
- Rule 11 (one-call trend): update "then use compute_totals with group_by='month'" to "then use code_execution to aggregate by month"
- Add structured output rule (see Section 8c):
  > **Structured output**: When your code_execution computes a result table, ALWAYS print the final structured data on the LAST line of stdout as: `STRUCTURED_RESULT:{"headers": [...], "rows": [[...], ...]}`

When `CODE_EXECUTION_ENABLED = False`:
- No changes (current prompt behavior)

**Implementation**: Pass `settings.CODE_EXECUTION_ENABLED` as a parameter to `build_query_agent_prompt`.

**AnalysisAgent prompt** (`build_analysis_agent_prompt`):

The current prompt also hardcodes `tool_names` from `ANALYSIS_TOOLS` (line 182) and references specific tools in `type_guidance` dict and Rules 1, 12.

When `CODE_EXECUTION_ENABLED = True`:
- Replace "## Available Tools" section with "## Code Execution" section
- `type_guidance` dict: replace tool-specific guidance with code_execution guidance
  - comparison: "Write Python code to compute absolute and percentage changes"
  - trend: "Write Python code to calculate period-over-period changes"
  - top_n: "Write Python code to sort and extract top/bottom N items"
  - aggregation: "Write Python code to compute totals and averages"
- Rules 1, 12: replace analysis tool names with code_execution reference
- Add structured output rule (same as QueryAgent — see Section 8c)

When `CODE_EXECUTION_ENABLED = False`:
- No changes (current prompt behavior)

**Implementation**: Pass `settings.CODE_EXECUTION_ENABLED` as a parameter to `build_analysis_agent_prompt`.

**Sandbox library availability**: The Anthropic sandbox pre-installs pandas, numpy, scipy, matplotlib, sympy, and more. Verify against [docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool) during implementation.

### 7. Logging

In both agent loops, log code execution blocks for Langfuse observability:

```python
# After receiving response, before processing tool blocks
code_exec_results = extract_code_execution_results(response)
for cer in code_exec_results:
    if cer["type"] == "code_written":
        logger.info("Agent turn %d — code_execution code:\n%s", turn, cer["code"])
    elif cer["type"] == "code_result":
        logger.info("Agent turn %d — code_execution stdout:\n%s", turn, cer["stdout"])
        if cer["stderr"]:
            logger.warning("Agent turn %d — code_execution stderr:\n%s", turn, cer["stderr"])
```

### 8. Data Flow Preservation (Structured Output Convention)

**Problem**: The current pipeline passes structured `{headers, rows}` data from AnalysisAgent → ChartAgent → Frontend. With code execution replacing analysis tools, this structured data disappears — code execution output is just stdout text. This breaks table rendering and chart generation.

**Solution**: A structured output convention via prompt + stdout parsing. Code execution must produce the same `{headers, rows}` contract that analysis tools produce today.

#### 8a. Current data flow

```
QueryAgent → tool_results [{tool_name, result: {data: {headers, rows}}}]
    ↓
Orchestrator._separate_tool_results() → raw_tally_data + computed_data
    ↓
AnalysisAgent → analysis tools produce {headers, rows} → last_table_data
    ↓
ChartAgent → reads {headers, rows} → chart spec
    ↓
Frontend → DataTable + ChartRenderer
```

#### 8b. New data flow (with code execution)

```
QueryAgent → Tally tools (unchanged) + code_execution (stdout with STRUCTURED_RESULT)
    ↓
Orchestrator → extracts structured data from code_execution stdout as computed_data
    ↓
AnalysisAgent → code_execution (stdout with STRUCTURED_RESULT) → last_table_data
    ↓
ChartAgent → reads {headers, rows} → chart spec (unchanged)
    ↓
Frontend → DataTable + ChartRenderer (unchanged)
```

#### 8c. Prompt convention

Both agent prompts include this instruction when `CODE_EXECUTION_ENABLED = True`:

> **Structured output**: When your code_execution computes a result table, ALWAYS print the final structured data on the LAST line of stdout using this exact prefix format:
> ```
> STRUCTURED_RESULT:{"headers": ["Col1", "Col2"], "rows": [["row1_val1", 123], ["row2_val1", 456]]}
> ```
> - Headers = column names (strings)
> - Rows = list of lists, each matching header order
> - Numeric values must be numbers (not strings)
> - You may print other text (debug, intermediate steps) before this line — only the STRUCTURED_RESULT line is captured for table/chart rendering

#### 8d. Parsing in utils.py

```python
STRUCTURED_RESULT_PREFIX = "STRUCTURED_RESULT:"

def extract_structured_from_code_execution(response) -> dict | None:
    """Extract {headers, rows} from code_execution stdout if present.

    Looks for a line starting with STRUCTURED_RESULT: followed by JSON.
    Returns the parsed dict or None if not found/invalid.
    """
    for block in response.content:
        if block.type == "code_execution_tool_result":
            stdout = getattr(block, "stdout", "")
            # Search from last line backwards (convention: last line)
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

#### 8e. Integration into QueryAgent

After receiving a response with code execution results, capture the structured data as a synthetic tool result so the orchestrator's `_separate_tool_results` can pick it up:

```python
# After processing code execution blocks in QueryAgent
structured = extract_structured_from_code_execution(response)
if structured:
    tool_results.append({
        "tool_name": "code_execution",
        "tool_input": {},
        "result": {"success": True, "data": structured},
    })
```

#### 8f. Integration into Orchestrator

Add `"code_execution"` to `_COMPUTED_TOOL_NAMES` so `_separate_tool_results` treats it as computed data:

```python
_COMPUTED_TOOL_NAMES = {
    "compute_totals", "compute_trend", "compute_period_comparison",
    "compute_percentage_change", "sort_by_field",
    "code_execution",  # structured output from code execution
}
```

This means the AnalysisAgent receives code_execution structured data as `computed_data` — the same path it gets `compute_totals` results today.

#### 8g. Integration into AnalysisAgent

Replace the current analysis-tool-based table capture with code execution parsing:

```python
# After processing response in AnalysisAgent
if settings.CODE_EXECUTION_ENABLED:
    structured = extract_structured_from_code_execution(response)
    if structured and "headers" in structured and "rows" in structured:
        last_table_data = {"headers": structured["headers"], "rows": structured["rows"]}
        # Set type-specific table data based on query_type
        if query_type == "top_n":
            ranked_table_data = last_table_data
        elif query_type == "trend":
            trend_table_data = last_table_data
        elif query_type == "comparison":
            comparison_table_data = last_table_data
```

#### 8h. Fallback

If `extract_structured_from_code_execution` returns `None` (LLM didn't follow convention, JSON parse error, etc.):
- AnalysisAgent falls back to `last_table_data = {"headers": [], "rows": []}`
- Orchestrator falls back to raw Tally data for table rendering
- ChartAgent gets empty data → `chart = None`
- Frontend still renders the text response, just without a structured table/chart

This is a graceful degradation — the user still gets the text answer with correct computation.

### 9. Orchestrator Impact

The orchestrator's `_separate_tool_results` (line 252 of `orchestrator.py`) separates tool results into "raw Tally data" and "computed data" based on `_COMPUTED_TOOL_NAMES`.

**Change needed**: Add `"code_execution"` to `_COMPUTED_TOOL_NAMES` (see section 8f above).

With this change:
- Code execution structured results flow through the same path as `compute_totals` results
- AnalysisAgent receives them as `computed_data`
- No other orchestrator changes needed

### 10. Kill Switch Behavior

When `CODE_EXECUTION_ENABLED = False`:
- Tool lists revert to current behavior (ANALYSIS_TOOLS included, code_execution excluded)
- Tool loop uses `find_all_tool_use_blocks` (current function)
- Zero behavioral change from today

When `CODE_EXECUTION_ENABLED = True` (default):
- ANALYSIS_TOOLS excluded from tool lists, code_execution included
- Tool loop uses `find_custom_tool_use_blocks` (new function)
- Analysis tools code still exists and is callable if needed, just not offered to Claude

## File Change Summary

| File | Change |
|------|--------|
| `pyproject.toml` / `requirements.txt` | Upgrade anthropic SDK |
| `backend/config.py` | Add `CODE_EXECUTION_ENABLED` |
| `backend/agents/query_agent.py` | Conditional tool list, use `find_custom_tool_use_blocks`, log code execution, capture structured output from code_execution, conditional message append |
| `backend/agents/analysis_agent.py` | Same pattern as query_agent + structured output capture for table data |
| `backend/agents/orchestrator.py` | Add `"code_execution"` to `_COMPUTED_TOOL_NAMES` |
| `backend/agents/utils.py` | Add `find_custom_tool_use_blocks`, `extract_code_execution_results`, `extract_structured_from_code_execution` |
| `backend/agents/prompts.py` | Conditional prompts: code_execution rules + structured output convention when enabled |
| `tests/unit/test_utils.py` | Tests for new util functions (including structured output parsing) |
| `tests/unit/test_query_agent.py` | Tests for code execution block handling |
| `tests/unit/test_analysis_agent.py` | Tests for code execution block handling + structured table capture |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SDK upgrade breaks existing code (35-version jump) | Review SDK changelog for breaking changes. Run full test suite after upgrade before any other changes. |
| Code execution adds latency | Sandbox is fast (sub-second for simple scripts). Monitor via Langfuse. |
| Claude writes buggy Python | Deterministic errors are debuggable, unlike mental math errors. stderr is logged. |
| Anthropic sandbox outage | Kill switch reverts to analysis tools instantly |
| LLM doesn't follow structured output convention | Graceful degradation: falls back to raw Tally data for tables, text response still rendered. Prompt is explicit about format. |
| Token cost increase from code in message history | Code execution responses (code + stdout) are appended to message history. Monitor token usage via Langfuse. Offset: fewer analysis tool round-trips. |
| `response.content` serialization with new block types | Verify session persistence / Langfuse tracing doesn't break when `response.content` contains `ServerToolUseBlock` / `CodeExecutionToolResultBlock` objects. Current code passes `response.content` as-is (list of Block objects), which the SDK handles. |
| Tests checking tool list composition break | Identify affected tests during implementation. Tests that mock `_ALL_QUERY_TOOLS` or assert tool list contents will need conditional logic or parameterization. |

## Testing Strategy

1. **SDK upgrade** — review changelog, run existing 820 tests, expect all pass
2. **Unit tests** — mock responses with server_tool_use/code_execution_tool_result blocks, verify loop handles them correctly
3. **Integration** — existing mock Tally tests should still pass (code execution is additive)
4. **Kill switch test** — set `CODE_EXECUTION_ENABLED=False`, verify all existing tests pass unchanged
5. **Manual validation** — re-run the stock coverage query against live Tally, compare accuracy vs the be_run12.log baseline (TP-Link WiFi Router: should be ~164 days, not 55)

## Manual Test Scenario

Query: "Which items are running low on stock based on last 6 months of sales? Stock should cover 60 days of average sales."

Expected behavior with code execution:
1. Agent calls `get_stock_summary` + `get_sales_register` (Tally tools — unchanged)
2. Agent calls `code_execution` with Python that merges stock + sales, computes avg monthly sales, days cover, status
3. All arithmetic is deterministic — no mental math errors
4. TP-Link WiFi Router: 12 stock / 2.17 avg monthly = ~166 days (not 55)
