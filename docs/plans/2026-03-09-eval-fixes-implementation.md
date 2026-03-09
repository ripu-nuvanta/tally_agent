# Eval Fixes & Improvements — Implementation Plan

**Date**: 2026-03-09
**Design doc**: `docs/plans/2026-03-09-eval-fixes-design.md`

---

## Phase 1: Critical Fixes (Unblock Eval Accuracy)

### Task 1.1: Flatten multi-dataset ChatResponse data

**Files**: `backend/agents/orchestrator.py`

**Changes**:
1. Replace lines 159-162 (the `final_data` logic) with a flattening function:
```python
# After line 130 (data = raw_data)
# ...existing code...

# Replace the multi-dataset block (lines 159-162):
final_data = data
if all_datasets is not None and analysis_result is None:
    final_data = _flatten_datasets(all_datasets)
```

2. Add `_flatten_datasets()` function:
```python
def _flatten_datasets(datasets: list) -> list[dict]:
    """Flatten list[list[dict]] into list[dict] with _dataset_index marker."""
    flat = []
    for idx, dataset in enumerate(datasets):
        if isinstance(dataset, list):
            for record in dataset:
                if isinstance(record, dict):
                    record["_dataset_index"] = idx
                    flat.append(record)
                # Skip non-dict items
        elif isinstance(dataset, dict):
            dataset["_dataset_index"] = idx
            flat.append(dataset)
    return flat
```

**Acceptance criteria**:
- `ChatResponse(data=_flatten_datasets([[{"a":1}],[{"b":2}]]))` validates without error
- Existing single-dataset responses unchanged
- Add unit test: `test_flatten_datasets_merges_lists`
- Add e2e test: multi-tool-call response returns 200, not 500

**Dependencies**: None

---

### Task 1.2: Add date resolution patterns — month+year, FY, month ranges

**Files**: `backend/utils/date_utils.py`, `tests/unit/test_date_utils.py`

**Changes** (insert in `resolve_date_range()` before the final `return {"error": ...}`):

1. **Month name mapping** (add at module level):
```python
_MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2,
    "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
```

2. **Specific month + year pattern**: `"April 2025"`, `"jan 2026"`, `"march 2026"`
```python
month_year = re.match(r'^(\w+)\s+(\d{4})$', desc)
if month_year:
    month_name = month_year.group(1)
    year = int(month_year.group(2))
    month_num = _MONTH_NAMES.get(month_name)
    if month_num:
        last_day = calendar.monthrange(year, month_num)[1]
        return {
            "from_date": format_for_tally(date(year, month_num, 1)),
            "to_date": format_for_tally(date(year, month_num, last_day)),
            "description": f"{calendar.month_name[month_num]} {year}",
        }
```

3. **Specific FY pattern**: `"FY 2025-26"`, `"fy 25-26"`, `"FY 2025-2026"`
```python
fy_match = re.match(r'^fy\s+(\d{2,4})[-–](\d{2,4})$', desc)
if fy_match:
    start_year_str = fy_match.group(1)
    start_year = int(start_year_str)
    if start_year < 100:
        start_year += 2000
    end_year_str = fy_match.group(2)
    end_year = int(end_year_str)
    if end_year < 100:
        end_year += 2000
    return {
        "from_date": format_for_tally(date(start_year, 4, 1)),
        "to_date": format_for_tally(date(end_year, 3, 31)),
        "description": f"FY {start_year}-{end_year % 100:02d}",
    }
```

4. **Month range pattern**: `"April to June 2025"`, `"apr to jun 2025"`
```python
month_range = re.match(r'^(\w+)\s+to\s+(\w+)\s+(\d{4})$', desc)
if month_range:
    start_month = _MONTH_NAMES.get(month_range.group(1))
    end_month = _MONTH_NAMES.get(month_range.group(2))
    year = int(month_range.group(3))
    if start_month and end_month:
        last_day = calendar.monthrange(year, end_month)[1]
        return {
            "from_date": format_for_tally(date(year, start_month, 1)),
            "to_date": format_for_tally(date(year, end_month, last_day)),
            "description": f"{calendar.month_name[start_month]}-{calendar.month_name[end_month]} {year}",
        }
```

**Tests to add** (`tests/unit/test_date_utils.py`):
```
test_resolve_april_2025 -> 01-04-2025 to 30-04-2025
test_resolve_march_2026 -> 01-03-2026 to 31-03-2026
test_resolve_jan_2026_abbreviated -> 01-01-2026 to 31-01-2026
test_resolve_fy_2025_26 -> 01-04-2025 to 31-03-2026
test_resolve_fy_25_26_short -> 01-04-2025 to 31-03-2026
test_resolve_fy_2025_2026_long -> 01-04-2025 to 31-03-2026
test_resolve_april_to_june_2025 -> 01-04-2025 to 30-06-2025
test_resolve_case_insensitive -> "APRIL 2025" works
test_resolve_september_2025 -> handles "sept" abbreviation
```

**Acceptance criteria**:
- All 9 new tests pass
- Existing date resolution tests still pass
- `resolve_date_range("April 2025")` returns correct range (no error)

**Dependencies**: None

---

### Task 1.3: Generate and commit golden fixtures for manual_test_regression

**Files**: `tests/eval/golden/manual_test_regression.json` (new)

**Changes**:
1. Run `generate_golden.py` against live Tally to get TB, P&L, BS, sales register data
2. Structure as:
```json
{
  "profit_and_loss_this_month": { "headers": [...], "rows": [...] },
  "sales_register_fy": [{ "party": "...", "amount": ... }, ...],
  "trial_balance_q2": { ... },
  "trial_balance_q3": { ... },
  "sales_register_monthly": { ... }
}
```
3. Update scenario YAML `expect.ground_truth_key` fields to reference these keys

**Acceptance criteria**:
- `tests/eval/golden/manual_test_regression.json` exists and is valid JSON
- `collect.py` loads it automatically when no `--host` is passed

**Dependencies**: Requires live Tally access for generation

---

### Task 1.4: Auto-detect Tally host from config in collect.py

**Files**: `tests/eval/collect.py`

**Changes**:
In `main()`, after `args = parser.parse_args()`, add:
```python
# Auto-detect Tally from config if --host not provided
if not args.host:
    try:
        from backend.config import settings
        if settings.TALLY_HOST and settings.TALLY_HOST != "localhost":
            args.host = settings.TALLY_HOST
            args.port = settings.TALLY_PORT
            print(f"Auto-detected Tally at {args.host}:{args.port} from .env")
    except Exception:
        pass
```

**Acceptance criteria**:
- With `.env` containing `TALLY_HOST=192.168.18.219`, running `collect.py` without `--host` auto-fetches ground truth
- With default localhost config, gracefully skips (no crash)

**Dependencies**: None

---

## Phase 2: Quality Improvements (Improve Eval Scores)

### Task 2.1: Raise query agent tool call limit to 25

**Files**: `backend/agents/query_agent.py`

**Changes**:
- Line 51: Change `max_tool_calls: int = 10` to `max_tool_calls: int = 25`

**Acceptance criteria**:
- `QueryAgent().max_tool_calls == 25`
- Monthly trend queries (12 fetches) complete without hitting ceiling

**Dependencies**: None

---

### Task 2.2: Update query agent prompt — Claude can compute simple dates itself

**Files**: `backend/agents/prompts.py`

**Changes**: Replace rule 9 in `build_query_agent_prompt()`:
```python
9. **Date resolution**: For relative expressions like "this month", "last quarter", \
"YTD", "last 3 months", call the `resolve_date_range` tool. \
For specific months (e.g. "April 2025") or financial years (e.g. "FY 2025-26"), \
you can compute the dates directly: \
  - Month: 1st to last day (e.g. April 2025 = 01-04-2025 to 30-04-2025) \
  - FY: April 1 to March 31 (e.g. FY 2025-26 = 01-04-2025 to 31-03-2026) \
  - Quarter: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar \
This saves tool calls. Only use resolve_date_range when unsure.
```

Also update the `resolve_date_range` tool description in `tools.py`:
```python
"description": "Convert a relative date expression to exact DD-MM-YYYY dates using the Indian Financial Year calendar. Use ONLY for relative expressions like 'this month', 'last quarter', 'YTD'. For specific months ('April 2025') or FY ('FY 2025-26'), compute dates yourself to save tool calls."
```

**Acceptance criteria**:
- For "sales trend over 25-26 FY", Claude should NOT call `resolve_date_range` for each month
- Prompt text includes the self-compute guidance

**Dependencies**: Task 1.2 (date resolution still works as fallback)

---

### Task 2.3: Pass conversation context to orchestrator classification

**Files**: `backend/agents/orchestrator.py`, `backend/agents/prompts.py`

**Changes**:

1. **`orchestrator.py`**: Update `_classify` signature and implementation:
```python
async def _classify(self, user_message: str, session: SessionContext | None = None) -> dict:
```
Build messages with context:
```python
messages = []
if session and session.messages:
    # Last 4 messages for context
    recent = session.messages[-4:]
    for msg in recent:
        messages.append({"role": msg["role"], "content": msg["content"]})
messages.append({"role": "user", "content": user_message})
```

2. **`orchestrator.py`**: Update `process_query` line 79:
```python
classification = await self._classify(user_message, session)
```

3. **`prompts.py`**: Add to orchestrator prompt after date rules:
```
## Conversation Context

If conversation history is provided, use it to resolve ambiguous references:
- "results" likely refers to the report type from the previous query
- "compare Q2 and Q3" in context of P&L means compare P&L for those quarters
- "Top 10 customers" after discussing sales means top 10 by sales amount
- Avoid classifying as clarification_needed if context makes the intent clear
```

**Acceptance criteria**:
- "compare Q2 and Q3 results" after a P&L query is NOT classified as clarification_needed
- "Top 10 customers" after sales discussion is classified as top_n, not clarification_needed
- Existing tests still pass (session=None backward compatible)

**Dependencies**: None

---

### Task 2.4: Fix compute_totals crash on non-dict records

**Files**: `backend/agents/analysis_agent.py`

**Changes**: Add type guard at top of `_tool_compute_totals` (line 217):
```python
def _tool_compute_totals(records, numeric_fields, group_by=None):
    # Coerce non-dict records to dicts
    coerced = []
    for r in records:
        if isinstance(r, dict):
            coerced.append(r)
        elif isinstance(r, (int, float)):
            coerced.append({"value": r})
        elif isinstance(r, str):
            try:
                coerced.append({"value": float(r.replace(",", "").replace("₹", ""))})
            except ValueError:
                coerced.append({"label": r})
        else:
            coerced.append({"value": str(r)})
    records = coerced
    # ...rest of function unchanged
```

**Tests to add** (`tests/unit/test_analysis_agent.py`):
```
test_compute_totals_with_string_records
test_compute_totals_with_numeric_records
test_compute_totals_with_mixed_records
```

**Acceptance criteria**:
- `_tool_compute_totals(["100", "200"], ["value"])` returns `{"records": [{"value": 300}], ...}`
- No `AttributeError` on string input

**Dependencies**: None

---

### Task 2.5: Improve chart generation for trend/comparison/top_n queries

**Files**: `backend/agents/orchestrator.py`, `backend/agents/prompts.py`

**Changes**:

1. **Orchestrator fallback**: After line 154, add:
```python
# Auto-enable chart for chart-worthy query types
if not requires_chart and query_type in ("trend", "comparison", "top_n"):
    requires_chart = True
    logger.info("Orchestrator — auto-enabling chart for query_type=%s", query_type)
```

2. **Prompt update** (orchestrator): Add to output format section:
```
Note: Always set requires_chart=true for trend, comparison, and top_n queries.
These query types inherently benefit from visual representation.
```

**Acceptance criteria**:
- "sales trend over FY" produces a chart
- "compare Q2 and Q3" produces a chart
- "Top 10 customers" produces a chart

**Dependencies**: None

---

### Task 2.6: Improve data table extraction from tool results

**Files**: `backend/agents/orchestrator.py`

**Changes**: Update `_extract_all_data()` to better extract structured data:
```python
def _extract_all_data(tool_results: list[dict]) -> list:
    data_list = []
    for tr in tool_results:
        result = tr.get("result", {})
        if result.get("success") is True and result.get("data") is not None:
            data = result["data"]
            # Handle ReportResponse-style dicts (headers/rows)
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                # Convert to list[dict] for consistent handling
                rows_as_dicts = []
                for row in data["rows"]:
                    rows_as_dicts.append(dict(zip(data["headers"], row)))
                data_list.append(rows_as_dicts)
            else:
                data_list.append(data)
    return data_list
```

**Acceptance criteria**:
- ReportResponse data (TB, P&L, BS) gets converted to `list[dict]` for the `data` field
- Frontend DataTable can render the result

**Dependencies**: None

---

## Phase 3: Eval Framework Improvements

### Task 3.1: Add Langfuse observability

**Files**: `pyproject.toml`, `backend/config.py`, `backend/main.py`

**Changes**:

1. **`pyproject.toml`**: Add dependencies:
```
langfuse = ">=2.0"
opentelemetry-instrumentation-anthropic = ">=0.1"
```

2. **`config.py`**: Add optional settings:
```python
LANGFUSE_PUBLIC_KEY: str = ""
LANGFUSE_SECRET_KEY: str = ""
LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
```

3. **`main.py`**: In `lifespan`, add instrumentation:
```python
if settings.LANGFUSE_PUBLIC_KEY:
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    AnthropicInstrumentor().instrument()
    logger.info("Langfuse instrumentation enabled")
```

**Acceptance criteria**:
- With `LANGFUSE_PUBLIC_KEY` set, traces appear in Langfuse dashboard
- Without it, no instrumentation (no errors, no overhead)
- All existing tests pass (no import errors)

**Dependencies**: None

---

### Task 3.2: Add full eval logging (agent trace in transcripts)

**Files**: `backend/agents/query_agent.py`, `backend/agents/orchestrator.py`, `tests/eval/collect.py`

**Changes**:

1. Add `tool_call_trace` to orchestrator result:
```python
# In process_query, build trace from query_agent + analysis_agent results
trace = []
for tr in tool_results:
    trace.append({
        "agent": "query",
        "tool_name": tr["tool_name"],
        "tool_input": tr["tool_input"],
        "success": tr["result"].get("success", False),
        "error": tr["result"].get("error"),
    })
# Add to return dict
return { ..., "trace": trace }
```

2. In `collect.py`, capture trace from API response (requires backend to expose it). Alternative: capture trace server-side via logging and read from log. Simpler approach: just log to file.

For MVP: Use structured logging in query_agent/orchestrator. The collect phase reads backend logs after each turn.

**Acceptance criteria**:
- Transcript JSON includes `agent_trace` field per turn
- Trace shows which tools were called and whether they succeeded

**Dependencies**: None

---

### Task 3.3: Full message screenshots in eval collector

**Files**: `tests/eval/collect.py`

**Changes**: After line 265 (existing table screenshot), add:
```python
# Full message screenshot (text + table + chart)
full_path = screenshots_dir / f"{scenario_name}_turn{turn_idx + 1}_full.png"
if await last_msg.count() > 0:
    # Use the inner content div for cleaner screenshot
    await last_msg.screenshot(path=str(full_path))
    turn_result["screenshot_full"] = str(full_path)
```

Note: `last_msg` is already defined at line 251 as `assistant_msgs.nth(last_msg_count - 1)`.

Move the screenshot code inside the existing `if last_msg_count > 0:` block.

**Acceptance criteria**:
- Each turn produces a `_full.png` screenshot
- Screenshot includes text, table, and chart together
- Existing chart/table screenshots still generated

**Dependencies**: None

---

### Task 3.4: Timestamped run folders

**Files**: `tests/eval/collect.py`, `tests/eval/judge.py`, `tests/eval/report.py`

**Changes**:

1. **`collect.py`**: In `main()`, create run folder:
```python
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_dir = RESULTS_DIR / f"run_{run_timestamp}"
run_dir.mkdir(parents=True, exist_ok=True)

# Create latest symlink
latest_link = RESULTS_DIR / "latest"
if latest_link.is_symlink() or latest_link.exists():
    latest_link.unlink()
latest_link.symlink_to(run_dir.name)
```
Update `screenshots_dir`, `save_transcript()` to use `run_dir`.

2. **`judge.py`**: Add `--run-dir` argument (default: `RESULTS_DIR / "latest"`):
```python
parser.add_argument("--run-dir", default=str(RESULTS_DIR / "latest"))
```

3. **`report.py`**: Same pattern — `--run-dir` with latest default.

**Acceptance criteria**:
- Running `collect.py` creates `tests/eval/results/run_YYYYMMDD_HHMMSS/`
- `latest` symlink points to most recent run
- `judge.py` and `report.py` work with `--run-dir` or default to `latest`

**Dependencies**: None

---

## Phase 4: Test Infrastructure (Regression Prevention)

### Task 4.1: Frontend tests using real eval response fixtures

**Files**: `frontend/src/__tests__/fixtures/eval_responses.json` (new), `frontend/src/__tests__/EvalResponses.test.tsx` (new)

**Changes**:

1. Create fixture file with 5 representative responses:
```json
[
  {
    "name": "profit_and_loss_response",
    "message": "Here is the P&L for March 2026...",
    "data": [{"account": "Sales", "amount": -4034350}, ...],
    "chart": null
  },
  {
    "name": "sales_trend_response",
    "message": "Sales trend for FY 2025-26...",
    "data": [{"month": "Apr", "sales": 500000}, ...],
    "chart": {"chart_type": "line", "title": "Sales Trend", "data": [...], "config": {...}}
  },
  {
    "name": "top_10_customers",
    "message": "Top 10 customers by sales...",
    "data": [{"customer": "HCODE", "amount": 2000000}, ...],
    "chart": {"chart_type": "bar", ...}
  },
  {
    "name": "quarterly_comparison",
    "message": "Comparison of Q2 vs Q3...",
    "data": [{"item": "Sales", "Q2": -1500000, "Q3": -1800000, "change": "-20%"}],
    "chart": {"chart_type": "grouped_bar", ...}
  },
  {
    "name": "multi_dataset_response",
    "message": "Here are the results...",
    "data": [{"name": "A", "_dataset_index": 0}, {"name": "B", "_dataset_index": 1}],
    "chart": null
  }
]
```

2. Write tests:
```tsx
describe("EvalResponses", () => {
  test.each(fixtures)("renders $name without error", (fixture) => { ... })
  test("DataTable renders multi-column data from eval", () => { ... })
  test("ChartRenderer handles line chart from eval", () => { ... })
  test("ChartRenderer handles grouped_bar from eval", () => { ... })
  test("MessageBubble renders text + table + chart", () => { ... })
})
```

**Acceptance criteria**:
- 5+ new frontend tests pass
- Tests use realistic data shapes from actual eval runs
- No new npm dependencies needed

**Dependencies**: Phase 1 fixes (to know the correct data shapes)

---

### Task 4.2: E2E mock tests for failure scenarios

**Files**: `tests/e2e/test_chat_pipeline.py`, `tests/e2e/conftest.py`

**Tests to add**:

1. **`test_multi_dataset_response_no_500`**: Two tool calls succeed, response validates:
```python
set_responses(
    orchestrator_responses=[make_classification_response("comparison")],
    query_agent_responses=[
        make_tool_call_response("get_sales_register", {"from_date": "01-07-2025", "to_date": "30-09-2025"}),
        make_tool_call_response("get_sales_register", {"from_date": "01-10-2025", "to_date": "31-12-2025"}),
        make_text_response("Here is the comparison of Q2 vs Q3 sales."),
    ],
)
response = await client.post("/api/chat", json={"message": "Compare Q2 and Q3 sales"})
assert response.status_code == 200
```

2. **`test_date_resolution_month_name`**: Query agent calls `resolve_date_range("April 2025")`:
```python
# Mock Claude calling resolve_date_range with a month name
set_responses(
    orchestrator_responses=[make_classification_response("simple_lookup")],
    query_agent_responses=[
        make_tool_call_response("resolve_date_range", {"description": "April 2025"}),
        make_tool_call_response("get_profit_and_loss", {"from_date": "01-04-2025", "to_date": "30-04-2025"}),
        make_text_response("P&L for April 2025."),
    ],
)
response = await client.post("/api/chat", json={"message": "P&L for April 2025"})
assert response.status_code == 200
```

3. **`test_graceful_tool_limit_exceeded`**: Verify graceful degradation when limit hit.

4. **`test_compute_totals_string_input_no_crash`**: Direct test of analysis tool.

**Acceptance criteria**:
- All 4 new e2e tests pass
- No 500 errors from Pydantic validation
- Tests use existing mock infrastructure (no new test deps)

**Dependencies**: Phase 1 (Task 1.1, 1.2) must be complete

---

## Phase 5: Perfect manual_test_regression

### Task 5.1: Run eval and verify all 5 turns succeed

**Pre-requisites**: All Phase 1+2 fixes deployed.

**Steps**:
1. Start backend: `uvicorn backend.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Run scenario:
```bash
PYTHONPATH=. python tests/eval/collect.py \
  --scenario manual_test_regression \
  --frontend-url http://localhost:5173
```
4. Check transcript for:
   - [ ] Turn 1 (P&L this month): has_table=true, no 500, correct month dates
   - [ ] Turn 2 (sales trend): has_table=true, has_chart=true, line chart
   - [ ] Turn 3 (compare Q2/Q3): has_table=true, has_chart=true, no clarification
   - [ ] Turn 4 (Top 10): has_table=true, has_chart=true, bar chart
   - [ ] Turn 5 (HCODE trend): has_table=true, has_chart=true, line chart
5. Run judge:
```bash
PYTHONPATH=. ANTHROPIC_API_KEY=<key> python tests/eval/judge.py
```
6. Check scores: all dimensions >= 4

**Acceptance criteria**:
- 0 turns with 500 errors
- 0 clarification requests
- 5/5 turns produce structured data (table)
- 3/5 turns produce charts (turns 2, 3, 4 or 5)
- All judge scores >= 4

**Dependencies**: All Phase 1+2 tasks

---

### Task 5.2: Fix any remaining issues found in Task 5.1

This is a buffer task. After the eval run in 5.1, if any turns still fail:
- Debug using transcript + backend logs
- Apply targeted fixes
- Re-run eval to verify

**Files**: TBD based on findings

**Dependencies**: Task 5.1

---

## Dependency Graph

```
Phase 1 (Critical):
  1.1 (flatten data)     ─┐
  1.2 (date resolution)  ─┼── Phase 2 ──── Phase 5
  1.3 (golden fixtures)  ─┤
  1.4 (auto-detect Tally)─┘

Phase 2 (Quality):
  2.1 (raise tool limit) ─┐
  2.2 (prompt update)    ─┤
  2.3 (context classify) ─┼── Phase 5
  2.4 (compute_totals)   ─┤
  2.5 (chart generation) ─┤
  2.6 (data extraction)  ─┘

Phase 3 (Eval tooling):     Independent, can run in parallel
  3.1 (Langfuse)
  3.2 (eval logging)
  3.3 (full screenshots)
  3.4 (run folders)

Phase 4 (Tests):            Depends on Phase 1
  4.1 (frontend fixtures)
  4.2 (e2e mock tests)

Phase 5 (Validation):      Depends on Phase 1 + 2
  5.1 (run eval)
  5.2 (fix remaining)
```

---

## Summary: Files Modified Per Phase

| Phase | Files Modified | Files Created |
|-------|---------------|--------------|
| Phase 1 | `orchestrator.py`, `date_utils.py`, `collect.py`, `test_date_utils.py` | `golden/manual_test_regression.json` |
| Phase 2 | `query_agent.py`, `prompts.py`, `orchestrator.py`, `analysis_agent.py`, `tools.py` | `test_analysis_agent.py` additions |
| Phase 3 | `pyproject.toml`, `config.py`, `main.py`, `collect.py`, `judge.py`, `report.py` | — |
| Phase 4 | `test_chat_pipeline.py` | `eval_responses.json`, `EvalResponses.test.tsx` |
| Phase 5 | TBD | — |
