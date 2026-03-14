# Chart Rendering Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Status:** COMPLETE (2026-03-14) — 15 commits (3b7c9cc..2fc5d0b), 731 BE + 116 FE + 48 PW = 895 tests

### Post-Plan Fixes (from eval run)
- FE axios timeout: 120s → 180s (`frontend/src/api/client.ts`)
- Code execution logging: USED/NOT USED + STRUCTURED_RESULT captured/missing (`analysis_agent.py`)
- Prompt compliance: CRITICAL rule for mandatory code_execution (`prompts.py`)
- Markdown table parsing fallback: parses markdown tables when code_execution is skipped (`analysis_agent.py`)
- Eval scenario expanded: `stock_reorder_mock.yaml` → 7-turn chart rendering test
- 3 new Playwright fixtures: stock_reorder_table_only, monthly_trend_dual_axis, top_customers_filtered

### Phase 13b Fixes (from eval run 17 — 2026-03-14)

Root cause investigation of stock_reorder_mock eval revealed 3 chart bugs + 2 robustness improvements:

**Bug fixes:**
- B1: `_format_pie_data` hardcoded `value_idx=1` → picks text column "Group" instead of numeric "Amount". Fixed to scan for first numeric column dynamically.
- B2: `_to_numeric` didn't strip markdown bold markers (`**`). `float("**-483350**")` → 0.0. Added `.replace("*", "")`.
- B3: Orchestrator auto-enabled charts for aggregation queries, ignoring user's "show as a table" intent. Added `_has_table_intent()` helper with 7 patterns.

**Robustness:**
- C1: `_parse_markdown_table` now strips `*` from headers and cells after parsing — defense in depth for bold markers.
- C3: Strengthened Rule 14 in AnalysisAgent prompt with concrete Python example showing how to print BOTH markdown table AND STRUCTURED_RESULT JSON.

**Tests:** 608 unit (up from 591 — +17 new tests)

**Files modified:** `chart_agent.py`, `orchestrator.py`, `analysis_agent.py`, `prompts.py`, `test_chart_agent.py`, `test_orchestrator.py`, `test_analysis_agent.py`

**Known remaining issues (for future phases):**
- Turn 7 truncation: QueryAgent uses prior conversation data (0 tool calls), AnalysisAgent skipped, max_tokens=1024 truncates. See architecture exploration doc.
- STRUCTURED_RESULT inconsistency: Model prints markdown but not JSON in 5/6 turns. Prompt improvement (C3) applied, needs eval validation.

**Goal:** Fix 6 chart rendering bugs so ChartAgent produces correct, readable charts (or skips charts when table_only is appropriate).

**Architecture:** All fixes are in `chart_agent.py` (rule-based, no API calls) and `prompts.py` (AnalysisAgent prompt guidance). The ChartAgent pipeline: `_select_chart_type()` → `_format_chart_data()` → `_build_config()`. Three data-flow bugs and one prompt improvement.

**Tech Stack:** Python, pytest. No external dependencies.

---

## File Map

| File | Responsibility | Changes |
|------|---------------|---------|
| `backend/agents/chart_agent.py` | Rule-based chart type selection + Recharts data formatting | Tasks 1-4 |
| `backend/agents/prompts.py` | AnalysisAgent system prompt (chart guidance) | Task 5 |
| `tests/unit/test_chart_agent.py` | Unit tests for all chart_agent functions | Tasks 1-4 tests |
| `tests/unit/test_prompts.py` | Unit tests for prompt content | Task 5 test |

---

## Chunk 1: Chart Data Fixes

### Task 1: Honor `table_only` suggestion in `_select_chart_type()`

**Bug:** When AnalysisAgent returns `chart_suggestion="table_only"`, line 117 skips it (`suggestion != "table_only"`) and falls through to query_type inference, which returns `"bar"` or `"pie"`. The suggestion is silently ignored.

**Files:**
- Modify: `backend/agents/chart_agent.py:106-118`
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write the failing test**

```python
# In tests/unit/test_chart_agent.py, in class TestSelectChartType:

def test_table_only_suggestion_is_honored(self):
    """table_only suggestion should return table_only, not defer to query_type."""
    rows = [[1], [2], [3]]
    assert _select_chart_type("table_only", "comparison", rows) == "table_only"
    assert _select_chart_type("table_only", "top_n", rows) == "table_only"
    assert _select_chart_type("table_only", "aggregation", rows) == "table_only"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_chart_agent.py::TestSelectChartType::test_table_only_suggestion_is_honored -v`
Expected: FAIL — returns `"grouped_bar"`, `"bar"`, `"pie"` instead of `"table_only"`

- [x] **Step 3: Update existing test that asserts the wrong behavior**

The existing `test_table_only_suggestion_defers_to_query_type` (line ~60) asserts the WRONG behavior. Delete or update it:

```python
# DELETE this test (it asserts the bug):
# def test_table_only_suggestion_defers_to_query_type(self):
#     rows = [[1], [2], [3]]
#     assert _select_chart_type("table_only", "comparison", rows) == "grouped_bar"
```

- [x] **Step 4: Fix `_select_chart_type()` to honor `table_only`**

In `backend/agents/chart_agent.py`, change line 117 from:

```python
    if suggestion in valid_types and suggestion != "table_only":
        return suggestion
```

to:

```python
    if suggestion in valid_types:
        return suggestion
```

This makes `table_only` a first-class suggestion that ChartAgent respects. The `execute()` method already handles `chart_type == "table_only"` by returning `None` (line 62-63).

- [x] **Step 5: Run tests to verify**

Run: `pytest tests/unit/test_chart_agent.py -v --tb=short`
Expected: All pass (new test passes, old test deleted)

- [x] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: honor table_only chart suggestion instead of deferring to query_type"
```

---

### Task 2: Filter `_format_xy_data()` to only include numeric columns

**Bug:** `_format_xy_data()` includes ALL columns in chart data points. Text columns (e.g. "Status", "Group") are converted to `0.0` via `_to_numeric()`, polluting the chart with spurious zero-value bars. The `_identify_numeric_columns()` function correctly detects numeric columns for `y_keys` in config, but `_format_xy_data()` ignores this.

**Files:**
- Modify: `backend/agents/chart_agent.py:163-188` and line 67
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write the failing test**

```python
# In tests/unit/test_chart_agent.py, in class TestNonNumericColumnFiltering:

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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_chart_agent.py::TestNonNumericColumnFiltering::test_format_xy_data_excludes_non_numeric_columns -v`
Expected: FAIL — `_format_xy_data()` doesn't accept `numeric_cols` parameter

- [x] **Step 3: Add `numeric_cols` parameter to `_format_xy_data()`**

In `backend/agents/chart_agent.py`, change the function signature and filter logic:

```python
def _format_xy_data(
    headers: list[str], rows: list[list], numeric_cols: set[str] | None = None
) -> list[dict[str, Any]]:
    """Standard label/value format for bar and line charts."""
    data = []
    for row in rows:
        label = str(row[0]) if row else ""
        if label.lower() in ("total", "grand total"):
            continue
        point: dict[str, Any] = {"label": label}
        for i, header in enumerate(headers[1:], start=1):
            if header in _EXCLUDED_CHART_COLUMNS:
                continue
            if numeric_cols is not None and header not in numeric_cols:
                continue
            if i < len(row):
                point[header] = _to_numeric(row[i])
        data.append(point)
    return data
```

- [x] **Step 4: Pass `numeric_cols` from `_format_chart_data()` and `execute()`**

Update `_format_chart_data()` to accept and pass `numeric_cols`:

```python
def _format_chart_data(
    chart_type: str, headers: list[str], rows: list[list], numeric_cols: set[str] | None = None
) -> list[dict[str, Any]]:
    """Format rows into Recharts-compatible data points."""
    if chart_type == "pie":
        return _format_pie_data(headers, rows)
    return _format_xy_data(headers, rows, numeric_cols)
```

Update `execute()` to compute `numeric_cols` once and pass it through. Around lines 67-68:

```python
        numeric_cols = _identify_numeric_columns(headers, rows)
        chart_data = _format_chart_data(chart_type, headers, rows, numeric_cols)
        config = _build_config(chart_type, headers, rows)
```

- [x] **Step 5: Run tests to verify**

Run: `pytest tests/unit/test_chart_agent.py -v --tb=short`
Expected: All pass. Existing `_format_xy_data` tests still pass because `numeric_cols=None` preserves old behavior.

- [x] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: filter text columns from chart data points in _format_xy_data"
```

---

### Task 3: Pattern-match secondary axis columns

**Bug:** Only the exact header `"Change %"` triggers dual-axis (composed chart). AnalysisAgent's code_execution produces varied names: `"MoM %"`, `"% vs Avg"`, `"MoM Change"`. Composed chart never triggers.

**Design decision (per user):** Instead of broadening pattern-matching in ChartAgent, standardize column names in the AnalysisAgent prompt so code_execution always outputs `"Change"` and `"Change %"` for delta columns. Then also broaden ChartAgent's detection as a safety net.

**Files:**
- Modify: `backend/agents/chart_agent.py:18-19,211-242,245-255`
- Modify: `backend/agents/prompts.py` (structured_rule_block)
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write the failing test for broader secondary axis detection**

```python
# In tests/unit/test_chart_agent.py, add new class:

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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestSecondaryAxisDetection -v`
Expected: FAIL — `"MoM %"` not detected as secondary

- [x] **Step 3: Implement pattern-based detection**

Replace the hardcoded detection in `_build_config()` and `_identify_numeric_columns()`. Add a helper:

```python
# At module level, replace _EXCLUDED_CHART_COLUMNS:

# Columns excluded from primary y-axis (absolute changes are noise on same scale)
_EXCLUDED_CHART_COLUMNS = {"Change"}

def _is_secondary_axis_column(header: str) -> bool:
    """Detect columns that belong on a secondary (percentage) axis."""
    h = header.lower().strip()
    # Percentage columns → secondary axis
    if "%" in header:
        return True
    return False

def _is_excluded_column(header: str) -> bool:
    """Detect columns that should be excluded from charts entirely."""
    h = header.lower().strip()
    if header in _EXCLUDED_CHART_COLUMNS:
        return True
    # Absolute change columns (not useful on same scale as primary values)
    change_patterns = ("change", "delta", "difference", "variance")
    # Only exclude if it looks like a change column but NOT a percentage
    if "%" not in header and any(p in h for p in change_patterns):
        return True
    return False
```

Update `_identify_numeric_columns()` to use `_is_excluded_column()` and `_is_secondary_axis_column()`:

```python
def _identify_numeric_columns(headers: list[str], rows: list[list]) -> set[str]:
    """Identify columns where >50% of values are numeric.
    Skips the first column (label/x-axis), excluded columns, and secondary axis columns.
    """
    if not rows or len(headers) < 2:
        return set(headers[1:])

    numeric_headers = set()
    for col_idx in range(1, len(headers)):
        header = headers[col_idx]
        if _is_excluded_column(header) or _is_secondary_axis_column(header):
            continue
        numeric_count = 0
        total = 0
        for row in rows:
            if col_idx < len(row):
                total += 1
                val = row[col_idx]
                if isinstance(val, (int, float)):
                    numeric_count += 1
                elif isinstance(val, str):
                    cleaned = val.replace("₹", "").replace(",", "").replace("%", "").replace(" ", "").strip()
                    try:
                        float(cleaned)
                        numeric_count += 1
                    except ValueError:
                        pass
        if total > 0 and numeric_count / total > 0.5:
            numeric_headers.add(header)
    return numeric_headers
```

Update `_build_config()` secondary detection:

```python
    # Detect secondary axis data (percentage columns)
    secondary_y_keys = [h for h in headers[1:] if _is_secondary_axis_column(h)]
```

- [x] **Step 4: Run tests to verify**

Run: `pytest tests/unit/test_chart_agent.py -v --tb=short`
Expected: All pass including new secondary axis tests

- [x] **Step 5: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: detect percentage/change columns for secondary axis and exclusion"
```

---

### Task 4: Add ChartAgent logging

**Bug:** ChartAgent has zero instrumentation — impossible to debug chart issues from backend logs.

**Files:**
- Modify: `backend/agents/chart_agent.py:1-10` and `execute()` method

- [x] **Step 1: Add logging to `execute()` method**

Add import at top of file:

```python
import logging

logger = logging.getLogger(__name__)
```

Add log lines in `execute()`:

```python
    def execute(self, data, query_type, requires_chart):
        if not requires_chart:
            return None

        table_data = _extract_table_data(data)
        if not table_data or not table_data.get("rows"):
            logger.info("ChartAgent — no table data, skipping chart")
            return None

        headers = table_data["headers"]
        rows = table_data["rows"]

        # ... (existing trim logic) ...

        chart_suggestion = data.get("chart_suggestion", "")
        chart_type = _select_chart_type(chart_suggestion, query_type, rows)

        logger.info(
            "ChartAgent — suggestion=%r, query_type=%s, rows=%d, selected=%s",
            chart_suggestion, query_type, len(rows), chart_type,
        )

        if chart_type == "table_only":
            logger.info("ChartAgent — table_only, returning None")
            return None

        # ... (existing format/config logic) ...

        if not config["y_keys"]:
            logger.info("ChartAgent — no numeric y_keys, returning None")
            return None

        logger.info(
            "ChartAgent — chart_type=%s, y_keys=%s, secondary=%s",
            chart_type, config["y_keys"], config.get("secondary_y_keys", []),
        )

        return { ... }
```

- [x] **Step 2: Run tests to verify nothing breaks**

Run: `pytest tests/unit/test_chart_agent.py -v --tb=short`
Expected: All pass (logging is side-effect only)

- [x] **Step 3: Commit**

```bash
git add backend/agents/chart_agent.py
git commit -m "feat: add logging to ChartAgent for chart pipeline debugging"
```

---

## Chunk 2: Prompt Standardization

### Task 5: Standardize STRUCTURED_RESULT column names in AnalysisAgent prompt

**Why:** Code_execution lets the model choose arbitrary column names (`"MoM Change"`, `"% vs Avg"`, `"Abs Change"`). ChartAgent was built for the old tools' fixed names (`"Change"`, `"Change %"`). Rather than making ChartAgent handle infinite variations, tell the model to use standard names.

**Files:**
- Modify: `backend/agents/prompts.py:286-292` (structured_rule_block, code_execution_enabled=True)
- Test: `tests/unit/test_prompts.py` (or `tests/unit/test_analysis_agent.py`)

- [x] **Step 1: Write the failing test**

```python
# In tests/unit/test_orchestrator.py or a new test:

def test_analysis_prompt_contains_column_naming_rules():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("trend", code_execution_enabled=True)
    assert "Change" in prompt and "Change %" in prompt
    assert "STRUCTURED_RESULT" in prompt
    assert "column naming" in prompt.lower() or "standard column" in prompt.lower()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_orchestrator.py::test_analysis_prompt_contains_column_naming_rules -v`
Expected: FAIL — no column naming rules in current prompt

- [x] **Step 3: Update the structured_rule_block in prompts.py**

In `build_analysis_agent_prompt()`, update the `structured_rule_block` (code_execution_enabled=True branch, around line 286):

```python
        structured_rule_block = """
14. **Structured output**: When your code_execution computes a result table, ALWAYS \
print the final structured data on the LAST line of stdout using this exact format:
STRUCTURED_RESULT:{"headers": ["Col1", "Col2"], "rows": [["val1", 123], ["val2", 456]]}
Headers must be strings. Row values: use numbers for numeric data (not strings). \
You may print other text before this line — only the STRUCTURED_RESULT line is \
captured for table/chart rendering.

15. **Standard column names for charts**: Use these EXACT header names in \
STRUCTURED_RESULT so the chart renderer can detect axes correctly:
   - Period-over-period absolute delta → "Change"
   - Period-over-period percentage delta → "Change %"
   - Do NOT use "MoM Change", "Abs Change", "MoM %", "% vs Avg", or other variations.
   - For status/flag columns (e.g. "Above"/"Below"), use the header "Status".
   - Keep the first column as the label/category (e.g. "Month", "Item", "Ledger")."""
```

- [x] **Step 4: Run tests to verify**

Run: `pytest tests/unit/ -v --tb=short -x`
Expected: All pass

- [x] **Step 5: Commit**

```bash
git add backend/agents/prompts.py tests/unit/test_orchestrator.py
git commit -m "feat: add standard column naming rules to AnalysisAgent prompt for charts"
```

---

### Task 6: Rule-based `table_only` override in ChartAgent

**Why:** Even with prompt guidance, AnalysisAgent may still suggest `bar` for a 7-column table with text. Add a safety net: if the table has many non-numeric columns, force `table_only`.

**Files:**
- Modify: `backend/agents/chart_agent.py:106-139`
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write the failing test**

```python
# In tests/unit/test_chart_agent.py:

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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_chart_agent.py::TestTableOnlyOverride -v`
Expected: FAIL — first test returns a chart instead of None

- [x] **Step 3: Add override logic in `execute()` method**

In `backend/agents/chart_agent.py`, add after computing `numeric_cols` but before `_format_chart_data`:

```python
        numeric_cols = _identify_numeric_columns(headers, rows)

        # Force table_only if too many non-numeric columns (charts are unreadable)
        non_label_headers = headers[1:]  # exclude first (label) column
        non_numeric_count = sum(1 for h in non_label_headers if h not in numeric_cols)
        if non_numeric_count >= 3:
            logger.info("ChartAgent — %d non-numeric columns, forcing table_only", non_numeric_count)
            return None

        chart_data = _format_chart_data(chart_type, headers, rows, numeric_cols)
```

- [x] **Step 4: Run tests to verify**

Run: `pytest tests/unit/test_chart_agent.py -v --tb=short`
Expected: All pass

- [x] **Step 5: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: force table_only when table has 3+ non-numeric columns"
```

---

## Final Verification

- [x] **Run all backend tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --tb=short 2>&1 | tail -5
```
Expected: 704+ tests pass, 0 failures

- [x] **Run frontend tests**

```bash
cd frontend && npm test
```
Expected: 111 tests pass

- [x] **Final commit (if any adjustments)**

```bash
git log --oneline -6  # Verify 6 clean commits
```
