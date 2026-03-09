# Eval Fixes & Improvements — Design Document

**Date**: 2026-03-09
**Status**: Draft
**Scope**: Fix 8 bugs + add 7 features to eval framework

---

## 1. Problem Summary

The first full eval run against `manual_test_regression` (5 turns) exposed systemic failures:

| Issue | Frequency | Impact |
|-------|-----------|--------|
| 500 errors from `ChatResponse.data` validation | 11x across eval run | Blocks all multi-tool-call responses |
| `resolve_date_range` errors | Every turn using month names / FY refs | Causes Claude to retry or hallucinate dates |
| Max tool call ceiling (10) hit | 15x | Truncates trend/comparison queries mid-fetch |
| Clarification on follow-up turns | 3/5 manual_test turns | Breaks conversation flow |
| `compute_totals` crash on string input | 1x observed | Analysis agent errors out |
| No ground truth in judge | All turns | Judge scores factual accuracy without reference data |
| Few charts/tables generated | 4/5 turns missing charts | Low chart_quality and response_quality scores |

---

## 2. Architecture Changes

### 2.1 CRITICAL: ChatResponse Multi-Dataset Fix (#1)

**Problem**: `_extract_all_data()` in orchestrator returns `list[list[dict]]` when multiple tool calls succeed. Line 161 sets `final_data = all_datasets` which is `list[list[dict]]`. Pydantic rejects this for the `data: dict | list[dict] | None` field.

**Solution**: Flatten multi-dataset results in the orchestrator before returning.

- In `orchestrator.py` line 161, flatten `all_datasets` by concatenating all inner lists into a single `list[dict]`.
- Each inner list is a dataset (e.g., Q1 sales vouchers, Q2 sales vouchers). Flattening merges them into one list.
- Add a `_period` or `_dataset_label` key to each record so downstream analysis can still distinguish them.
- This preserves the `list[dict]` type that `ChatResponse.data` expects.

**Alternative considered**: Widen `ChatResponse.data` to `dict | list[dict] | list[list[dict]] | None`. Rejected because the frontend `DataTable` component only handles `list[dict]` — widening the type would push the problem to the frontend.

**Files**: `backend/agents/orchestrator.py` (lines 119-162)

### 2.2 CRITICAL: Ground Truth Auto-Collection (#2)

**Problem**: `collect.py` only fetches golden data when `--host` is passed. Without ground truth, the judge scores factual accuracy blindly.

**Solution**: Two-pronged approach:

1. **Pre-generated golden fixtures**: Run `generate_golden.py` once against live Tally, save to `tests/eval/golden/manual_test_regression.json`. Commit the fixture.
2. **Auto-detect Tally from `.env`**: In `collect.py`, read `TALLY_HOST`/`TALLY_PORT` from env/config when `--host` is not explicitly passed. If Tally is reachable, collect live ground truth automatically.

**Files**: `tests/eval/collect.py`, `tests/eval/golden/manual_test_regression.json` (new)

### 2.3 HIGH: Date Resolution Expansion (#3)

**Problem**: `resolve_date_range()` only handles: Q1-Q4, this/last month/quarter/FY, YTD, last N months. Claude calls it with "April 2025", "March 2026", "FY 2025-26", "January 2026" — all return errors.

**New patterns to add**:

| Pattern | Examples | Resolution |
|---------|----------|------------|
| Month + Year | "April 2025", "march 2026", "jan 2026" | 1st to last day of that month |
| FY reference | "FY 2025-26", "fy 25-26", "FY 2025-2026" | Apr 1 of start year to Mar 31 of end year |
| Month range | "April to June 2025", "Apr-Jun 2025" | 1st of start month to last day of end month |
| Full year | "2025", "2026" | Treat as FY: Apr 1 to Mar 31 |

**Implementation**: Add regex patterns to `resolve_date_range()` in `date_utils.py` (before the final error return):

```python
# Month + Year: "April 2025", "jan 2026"
month_year = re.match(r'^(january|february|...|december|jan|feb|...|dec)\s+(\d{4})$', desc)

# FY reference: "FY 2025-26", "fy 25-26"
fy_match = re.match(r'^fy\s+(\d{4})[-–](\d{2,4})$', desc)

# Month range: "April to June 2025"
month_range = re.match(r'^(\w+)\s+to\s+(\w+)\s+(\d{4})$', desc)
```

**Files**: `backend/utils/date_utils.py` (add ~60 lines), `tests/unit/test_date_utils.py` (add ~30 tests)

### 2.4 HIGH: Query Agent Tool Call Ceiling (#4)

**Problem**: Monthly trends need 12 date resolutions + 12 Tally fetches = 24 tool calls, but the limit is 10.

**Multi-pronged fix**:

1. **Raise limit to 25**: `QueryAgent.__init__` default `max_tool_calls=25`.
2. **Smarter prompt**: Tell Claude it can compute simple dates itself (specific months, FY years) without calling `resolve_date_range`. Reserve the tool for relative expressions only ("this month", "last quarter").
3. **Batch-friendly date tool**: Add a `resolve_multiple_dates` tool that takes a list of descriptions and returns all resolved ranges in one call.

**Approach chosen**: Combination of (1) and (2). Raising the limit is safe since each tool call is fast (date resolution is local, Tally queries are ~200ms each). Updating the prompt to say "For specific months like 'April 2025' or FY years like 'FY 2025-26', compute the dates yourself. Only use resolve_date_range for relative expressions" reduces unnecessary tool calls by ~50%.

**Files**: `backend/agents/query_agent.py` (line 51), `backend/agents/prompts.py` (rule 9)

### 2.5 HIGH: Conversation Context for Classification (#5)

**Problem**: Orchestrator classifies queries in isolation. "Compare Q2 and Q3 results" gets classified as `clarification_needed` because it lacks context about what "results" means.

**Solution**: Pass the last 4 messages from session history to the orchestrator's classification call. The classifier prompt already says "today's date" — extend it with conversation context.

**Implementation**:
- `Orchestrator._classify()` takes an optional `session: SessionContext` parameter.
- Build messages array with last N session messages + new user message.
- Update `build_orchestrator_prompt()` to include a "Conversation context" section.

**Files**: `backend/agents/orchestrator.py` (lines 62-79, 172-203), `backend/agents/prompts.py` (orchestrator prompt)

### 2.6 MEDIUM: Analysis Agent `compute_totals` Type Guard (#6)

**Problem**: `_tool_compute_totals` at line 221 calls `rec.get(group_by, "")` but `rec` may be a string (when data is `list[str]` instead of `list[dict]`).

**Solution**: Add type guard at the top of `_tool_compute_totals`:

```python
def _tool_compute_totals(records, numeric_fields, group_by=None):
    # Coerce non-dict records
    records = [r if isinstance(r, dict) else {"value": r} for r in records]
    ...
```

**Files**: `backend/agents/analysis_agent.py` (line 213-233)

### 2.7 MEDIUM: Chart Generation Improvements (#7)

**Problem**: Orchestrator's `requires_chart` classification is often `false` for queries that should produce charts ("sales trend", "quarterly comparison").

**Fix**: Two changes:
1. **Orchestrator prompt**: Add explicit guidance: "Set `requires_chart: true` for trend, comparison, and top_n queries."
2. **Fallback chart detection**: In orchestrator, if `query_type in {trend, comparison, top_n}` AND data is available AND `requires_chart` was false, override to true. Trust the query type signal.

**Files**: `backend/agents/orchestrator.py` (line 155), `backend/agents/prompts.py` (orchestrator prompt)

### 2.8 MEDIUM: Table Data in Responses (#8)

**Problem**: Data often comes back in text only, not as structured `data` field.

**Root cause**: The orchestrator only populates `data` from tool results, but for simple_lookup the raw Tally data (ReportResponse dict with headers/rows) goes through fine. The issue is that `_extract_all_data` only captures `result["data"]` from tool calls — if the data is nested differently (e.g., report response has `headers`/`rows` at top level), it gets lost.

**Fix**: In `_extract_all_data`, also accept dicts that have `headers`/`rows` keys directly.

**Files**: `backend/agents/orchestrator.py` (lines 215-227)

---

## 3. New Features

### 3.1 Langfuse Observability (#9)

**What**: Auto-instrument all Claude API calls with OpenTelemetry + Langfuse.

**Architecture**:
- Add `langfuse` + `opentelemetry-instrumentation-anthropic` to `pyproject.toml`
- In `backend/main.py` lifespan, call `AnthropicInstrumentor().instrument()` if `LANGFUSE_PUBLIC_KEY` is set
- Add 3 env vars to `backend/config.py`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`
- Zero code changes to agent layer — instrumentation is automatic via monkey-patching

**Files**: `pyproject.toml`, `backend/config.py`, `backend/main.py`

### 3.2 Full Eval Logging (#10)

**What**: Log all tool calls, tool results, agent responses, and latencies per turn in the transcript.

**Architecture**:
- Add a `TraceCollector` class that captures: tool_name, tool_input, tool_result, latency_ms, agent (query/analysis/chart)
- Inject into `QueryAgent.execute()` and `AnalysisAgent.execute()` via an optional parameter
- Save trace in transcript under `turn_result["agent_trace"]`
- Format: `[{agent, tool_name, tool_input, tool_result_summary, latency_ms, timestamp}]`

**Files**: `backend/agents/query_agent.py`, `backend/agents/analysis_agent.py`, `tests/eval/collect.py`

### 3.3 Full Message Screenshots (#11)

**What**: Screenshot the entire last assistant message bubble (text + table + chart together), not just individual elements.

**Architecture**:
- After extracting the response in `collect_scenario()`, take a screenshot of the entire last `[class*='justify-start']` element.
- Save as `{scenario}_turn{N}_full.png`.
- Keep existing chart/table-specific screenshots for the judge's chart_quality dimension.

**Files**: `tests/eval/collect.py`

### 3.4 Timestamped Run Folders (#12)

**What**: Each eval run gets its own folder: `tests/eval/results/run_YYYYMMDD_HHMMSS/`

**Architecture**:
- Create run folder at start of `main()` in `collect.py`
- Pass `run_dir` through to `save_transcript()` and screenshot functions
- `judge.py` and `report.py` accept `--run-dir` argument (default: most recent run)
- Symlink `tests/eval/results/latest` -> most recent run folder

**Files**: `tests/eval/collect.py`, `tests/eval/judge.py`, `tests/eval/report.py`

### 3.5 Frontend Tests from Eval Responses (#13)

**What**: Use real API responses from eval transcripts as frontend test fixtures.

**Architecture**:
- Extract `response_message`, `table_data`, `chart_spec` from eval transcripts
- Create `frontend/src/__tests__/fixtures/eval_responses.json` with 5-10 representative responses
- Write tests: DataTable renders multi-column data, ChartRenderer handles bar/line/pie specs, MessageBubble renders combined text+table+chart
- Tests run in Vitest (no API needed)

**Files**: `frontend/src/__tests__/fixtures/eval_responses.json` (new), `frontend/src/__tests__/EvalResponses.test.tsx` (new)

### 3.6 E2E Mock Tests for Failure Scenarios (#14)

**What**: Mock-based e2e tests that reproduce exact eval failure modes.

**Tests to add**:
1. Multi-dataset response (2 tool calls succeed) -> no 500
2. Date resolution with "April 2025" -> correct range
3. Query agent hits tool call limit -> graceful degradation
4. `compute_totals` with string input -> no crash
5. Trend query with 12 months -> completes within tool limit

**Files**: `tests/e2e/test_chat_pipeline.py` (add ~5 tests), `tests/unit/test_date_utils.py` (add ~15 tests)

### 3.7 Perfect `manual_test_regression` (#15)

**Target scores**: 4-5 on all 5 dimensions across all 5 turns.

**Per-turn requirements**:
1. "P&L this month" -> P&L data with table, correct month dates
2. "sales trend over 25-26 FY" -> Monthly sales data with line chart, trend direction
3. "compare Q2 and Q3 results" -> Two-period comparison with grouped_bar chart, uses conversation context
4. "Top 10 customers" -> Ranked list with bar chart, sorted descending
5. "month-wise trend for hcode" -> Ledger-specific monthly data with line chart

**Validation**: Run eval scenario, check all 5 turns produce tables/charts, no 500s, no clarifications.

---

## 4. Testing Strategy

| Change | Unit Tests | Integration Tests | E2E Tests |
|--------|-----------|-------------------|-----------|
| Multi-dataset flatten | Test `_extract_all_data` with nested lists | Mock pipeline with 2 tool calls | `test_chat_pipeline.py` |
| Date resolution | 30+ patterns in `test_date_utils.py` | — | Via eval scenario |
| Tool call limit | — | — | Mock e2e with 12-month trend |
| Conversation context | Test `_classify` with session messages | — | Via eval scenario |
| `compute_totals` guard | Test with `list[str]` input | — | — |
| Chart generation | Test `_select_chart_type` overrides | — | Via eval scenario |
| Langfuse | Config test only (env vars load) | — | — |
| Eval logging | — | — | Manual run verification |
| Run folders | — | — | Manual run verification |

---

## 5. Implementation Phases

| Phase | Issues | Est. Effort | Unblocks |
|-------|--------|-------------|----------|
| **Phase 1**: Critical fixes | #1, #2, #3 | 3-4 hours | Eval accuracy |
| **Phase 2**: Quality improvements | #4, #5, #6, #7, #8 | 3-4 hours | Eval scores |
| **Phase 3**: Eval tooling | #9, #10, #11, #12 | 2-3 hours | Developer experience |
| **Phase 4**: Test infrastructure | #13, #14 | 2-3 hours | Regression prevention |
| **Phase 5**: Validation | #15 | 1-2 hours | Confidence |

Total estimated: 11-16 hours across phases.
