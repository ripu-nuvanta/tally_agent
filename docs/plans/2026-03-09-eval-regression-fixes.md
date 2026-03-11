# Eval Regression Fix Plan

## Context

The `manual_test_regression` eval run (run_20260309_224658) revealed 3 bugs causing 4 of 5 turns to underperform. Root causes identified from `be_run.log` analysis.

---

## Phase 1 — Initial Regression Fixes (DONE)

### Bug 1: Classifier JSON Parsing Failure (Turns 3 & 5) — DONE

**File**: `backend/agents/orchestrator.py`, line 224
**Fix**: Changed `re.match` → `re.search` in `_strip_markdown_fences` to extract JSON from fenced blocks even with trailing text.

### Bug 2: Chart Suggestion Extraction Fails on Bold Markdown (Turn 4) — DONE

**File**: `backend/agents/analysis_agent.py`, line 537
**Fix**: Added `re.sub(r'\*{1,2}', '', text)` to strip markdown formatting before chart keyword search. Added missing `import re`.

### Bug 3: QueryAgent Returns Markdown Tables (Turns 1, 3, 5) — DONE

**File**: `backend/agents/prompts.py`, line 144
**Fix**: Added rule #10 to `build_query_agent_prompt` instructing Claude to never output markdown pipe tables.

### Langfuse OTLP Setup — DONE

**File**: `backend/main.py`, lifespan function
**Fix**: Added TracerProvider + OTLPSpanExporter + global tracer setup. Endpoint corrected to `/api/public/otel/v1/traces`.

### Phase 1 Eval Results (run_20260310_103714)

| Turn | Query | Table | Chart | Factual | Quality | Coherence | Chart Score |
|------|-------|-------|-------|---------|---------|-----------|-------------|
| 1 | P&L this month | False | False | 3 | 4 | 5 | - |
| 2 | Sales trend FY 25-26 | True | True | 4 | 5 | 5 | 2 |
| 3 | Compare Q2 vs Q3 | True | True | 3 | 5 | 3 | 2 |
| 4 | Top 10 customers | True | False | 4 | 4 | 5 | - |
| 5 | Month-wise trend hcode | True | True | 4 | 5 | 5 | 2 |

**Progress**: Turns 2/3/5 now return structured data + charts. Turn 3 no longer triggers clarification. Quality/coherence strong (4-5). Charts score 2/5 due to new issues found below.

---

## Phase 2 — Chart & Data Fixes (DONE — commit 93bf5d2)

### Phase 2a: Critical Bug Fixes

#### Bug 4: ChartRenderer Plots All Data Keys, Ignores `y_keys` — DONE

**Turns affected**: 2, 3, 5 (chart_quality = 2)

**Root cause (two layers)**:

1. **Backend** (`chart_agent.py:_format_xy_data`): Includes ALL headers (including "Change", "Change %") in chart data points.
2. **Frontend** (`ChartRenderer.tsx`): Derives series from `Object.keys(data[0])` — ignores `config.y_keys`.

**Fix A (Backend)**: Filter excluded columns in `_format_xy_data`:
```python
_EXCLUDED_CHART_COLUMNS = {"Change", "Change %"}
# Skip headers in _EXCLUDED_CHART_COLUMNS when building data points
```

**Fix B (Frontend)**: Use `config.y_keys` when available, fall back to Object.keys.

#### Bug 5: `show_legend: false` Not Respected — DONE

**Fix**: `{config?.show_legend !== false && <Legend />}` in all chart branches.

#### Bug 6: Top-N Data Table Shows Only Aggregate Total — DONE

**Turn affected**: 4
**Fix**: Added `ranked_table_data` tracker in analysis_agent.py that captures `sort_by_field` results separately. All three return paths prefer ranked data for `top_n` queries.

#### Bug 7: Q3 Sales = Full-Year Total (Cumulative P&L) — DONE

**Turn affected**: 3
**Root cause**: Tally's P&L TYPE=Data ignores SVFROMDATE, returning inconsistent cumulative figures.
**Fix**: Added `profit_and_loss_period()` in `reports.py` — fetches two cumulative P&L reports (FY-start to period-end, FY-start to day-before-period-start) and subtracts. Queries starting from FY start (Q1, full year) remain single-request. Tool handler updated to use period-specific version.

#### Bug 8: Chart Title Defaults to "Change % by Period" — DONE

**Fix**: Three-layer fix:
1. `_generate_title` uses first non-excluded header (not Change/Change %)
2. Analysis agent prompt requests "Chart title:" line from Claude
3. `_extract_chart_title` extracts it; chart_agent prefers it over rule-based fallback

### Phase 2b: Chart UX Improvements

#### Enhancement 9: ComposedChart with Secondary Y-Axis for Change %

**Problem**: Trend/comparison charts should show primary metric (bars) + Change % (line on secondary axis). Currently Change % is either excluded or plotted at wrong scale.

**Design**:
- Use Recharts `ComposedChart` (already available in Recharts 3.7) to mix `<Bar>` + `<Line>` in one chart
- Primary Y-axis (left): absolute values in currency (₹) — for series like Sales, Revenue
- Secondary Y-axis (right): percentage scale (-100% to +100%) — for Change %
- Change % rendered as a `<Line>` on `yAxisId="right"`
- Absolute "Change" column excluded from chart (redundant with visual bar comparison)

**Backend changes** (`chart_agent.py`):
- New config fields: `secondary_y_keys: list[str]` (keys for right axis), `chart_type: "composed"`
- `_build_config` populates `secondary_y_keys: ["Change %"]` when trend/comparison data includes it
- `_format_xy_data` includes Change % in data points (parsed as numeric) but NOT Change

**Frontend changes** (`ChartRenderer.tsx`):
- Import `ComposedChart` from Recharts
- New branch for `chart_type === "composed"`:
  - `<YAxis yAxisId="left" orientation="left" tickFormatter={formatAmount} />`
  - `<YAxis yAxisId="right" orientation="right" tickFormatter={(v) => \`${v}%\`} />`
  - Primary keys → `<Bar yAxisId="left" ... />`
  - Secondary keys → `<Line yAxisId="right" type="monotone" ... />`

#### Enhancement 10: Distinct Colors for Multi-Series Charts

**Problem**: Turn 2 (single series) and Turn 3 (Q2 vs Q3) need visually distinct, thoughtful color assignments.

**Design**:
- Single series: solid indigo (current default OK)
- Two series comparison: indigo vs emerald (high contrast)
- Three+ series: use full palette with maximum visual separation
- Change % line: always dashed gray or orange (visually secondary)

**Implementation**:
- Backend `_build_config` already sends `colors` array — ensure it maps well
- Frontend: apply colors from config, use `strokeDasharray="5 5"` for Change % line

#### Enhancement 11: Smart Number Formatting (₹ in Thousands/Lakhs)

**Problem**: Y-axis shows raw numbers like `3764350` — hard to read. Should show `₹37.6L` or `₹3.8L`.

**Design**:
- Y-axis ticks: Auto-scale to thousands (K) or lakhs (L) based on max value
  - < ₹1,00,000 → show as-is with ₹ prefix
  - ₹1L – ₹1Cr → show in lakhs: `₹37.6L`
  - > ₹1Cr → show in crores: `₹1.2Cr`
- Tooltip: Full formatted amount `₹37,64,350`
- All amounts as whole numbers (no decimals) on axis; tooltip can have 2 decimals
- Percentage axis: whole numbers with % suffix

**Implementation**:
- New `formatAxisAmount(value: number): string` in `frontend/src/utils/format.ts`
- Wire to `<YAxis tickFormatter={formatAxisAmount} />` in ChartRenderer
- Wire `<Tooltip formatter={...} />` for full formatted amounts

#### Enhancement 12: Turn 3 Legend/Series Mismatch — DONE

**Fix**: Addressed by Enhancement 9 (ComposedChart) — Change % moves to secondary axis line, legend shows only visible series. Combined with Bug 4 fix (exclude Change from data), the grouped bar will show only Q2 and Q3.

### Phase 2 Test Results

| Suite | Count | Delta |
|-------|-------|-------|
| Backend unit | 386 | +19 |
| Frontend Vitest | 101 | +15 |
| Playwright visual | 36 | +6 |
| **Total** | **523** | **+40** |

New Playwright fixtures: `sales_trend_composed` (ComposedChart dual Y-axis), `top_customers_ranked` (ranked records + show_legend=false). All screenshots visually inspected across mobile/tablet/desktop.

---

## Phase 3 — Langfuse Observability (DONE)

### Completed:
- OTLP endpoint corrected to `/api/public/otel/v1/traces`
- Test script created at `scripts/test_langfuse.py`
- **Switched to BatchSpanProcessor** (SimpleSpanProcessor blocks event loop) — `backend/main.py` + `scripts/test_langfuse.py`
- **Pass tracer_provider explicitly** to `AnthropicInstrumentor().instrument(tracer_provider=provider)`
- **Added provider.shutdown()** in lifespan teardown for clean exit
- **Added missing pyproject.toml deps**: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` to langfuse extra
- **Verified**: Test script exports 2 spans successfully (HTTP 200 from cloud.langfuse.com)
- **Session grouping**: Chat endpoint sets `langfuse.session.id` + `langfuse.trace.metadata.company` on OTLP spans
- **Langfuse skill**: Installed via `npx skills add langfuse/skills --skill "langfuse" --yes`
- **CLAUDE.md**: Fixed `uv sync` → `uv sync --extra dev --extra langfuse` to prevent removing pytest/playwright

---

## Phase 4 — Accuracy Improvements & Agent Architecture (FUTURE)

### Option A: Model Upgrade (Sonnet → Opus)
- **Change**: `CLAUDE_MODEL=claude-opus-4-6` in `.env` (1-line config change)
- **Pros**: Better tool-calling accuracy, superior instruction following
- **Cons**: ~3-4x cost increase, +140% latency
- **Recommendation**: Test in staging first, measure accuracy delta

### Option B: Code Execution Capability
- **Change**: New `backend/agents/code_executor.py` with sandboxed Python execution
- **Pros**: Unbounded computation, fewer Claude turns, no API cost increase
- **Cons**: ~800 LOC, security surface area, needs review
- **Recommendation**: Prototype and validate security before integrating

### Option C: Agent Architecture Redesign (QueryAgent / AnalysisAgent Overlap)

**Problem identified in Phase 8 eval analysis (run_20260311_134758):**

QueryAgent and AnalysisAgent have overlapping tool sets — `_ALL_QUERY_TOOLS` in `query_agent.py:38` includes `ANALYSIS_TOOLS` (compute_totals, compute_trend, compute_period_comparison, etc.). This causes:

1. **Duplicate computation**: QueryAgent computes (3-4 tool calls), then Orchestrator unconditionally routes to AnalysisAgent which re-computes (2-3 calls) from the same data.
2. **Conflicting results**: QueryAgent produced Q2 total = ₹11,95,000 (all vouchers), AnalysisAgent produced Q2 SALES HARYANA = ₹8,95,000 (manual ledger extraction) — text/table mismatch in Turn 3.
3. **High latency**: Turn 3 took 75.8s with ~15 Tally calls due to double data fetching and computation.
4. **Wasted tokens/cost**: Both agents get the same data and independently reason about it.

**Evidence from be_run6.log:**
- Turn 2 (trend): QueryAgent calls get_sales_register + compute_totals + compute_trend. Then AnalysisAgent calls compute_totals + compute_trend again.
- Turn 3 (comparison): QueryAgent calls get_profit_and_loss ×2, get_sales_register ×2, get_purchase_register ×2, compute_totals ×3. Then AnalysisAgent calls compute_period_comparison + compute_totals ×2.
- Turn 4 (top_n): Similar pattern — QueryAgent fetches and computes, AnalysisAgent re-computes.

**Design options:**

**C1: Remove ANALYSIS_TOOLS from QueryAgent entirely**
- QueryAgent = data fetching only (TALLY_TOOLS + DATE_TOOLS)
- AnalysisAgent = sole computation authority
- Pros: Clean separation, no conflicts, ~50% fewer tool calls
- Cons: Simple queries (e.g. "what is cash balance?") that don't route to AnalysisAgent lose computation ability. Currently QueryAgent handles `simple_lookup` and `aggregation` types without AnalysisAgent.
- Risk: Breaking change — needs careful testing of all query types

**C2: Orchestrator passes "data-fetch-only" flag to QueryAgent**
- When Orchestrator knows query will route to AnalysisAgent (comparison/trend/top_n), it tells QueryAgent to skip computation
- QueryAgent prompt gets conditional rule: "Fetch raw data only — a specialist will handle computation"
- Pros: Minimal code change, preserves QueryAgent's computation for simple queries
- Cons: Prompt-based — model may still compute despite instruction

**C3: Merge QueryAgent and AnalysisAgent into single agent**
- One agent with all tools (Tally + Analysis + Date)
- Orchestrator routes directly; no handover overhead
- Pros: Eliminates duplicate computation entirely, simpler architecture
- Cons: Larger tool set may confuse model; loses specialization benefit; session context grows faster

**C4: Streaming handover with computed-data flag**
- QueryAgent returns `tool_results` with metadata: `{source: "tally_api"}` vs `{source: "computed"}`
- Orchestrator passes only `tally_api` results to AnalysisAgent, skipping already-computed data
- AnalysisAgent knows what's raw vs computed
- Pros: Preserves both agents, no lost capability
- Cons: Most complex to implement; still runs both agents

**Recommendation**: Start with C2 (lowest risk, testable via eval). If insufficient, move to C1 or C3. Evaluate alongside model upgrade (Option A) since a better model may reduce the need for agent specialization.

**Blocked on**: Eval results from Phase 8 prompt fixes — if prompt rules (exact ledger names, tool-only computation) significantly improve Turn 3 accuracy, the architectural change becomes lower priority.

---

## Files Modified (Phase 2) — commit 93bf5d2

| # | File | Changes |
|---|------|---------|
| 1 | `backend/agents/chart_agent.py` | Bug 4 (_EXCLUDED_CHART_COLUMNS), Bug 8 (_generate_title), Enh 9 (composed type, secondary_y_keys), Enh 10 (secondary_colors) |
| 2 | `backend/agents/analysis_agent.py` | Bug 6 (ranked_table_data), Bug 8 (_extract_chart_title), "composed" in valid suggestions |
| 3 | `backend/agents/prompts.py` | Bug 8 (Chart title: instruction in analysis prompt) |
| 4 | `backend/agents/tools.py` | Bug 7 (profit_and_loss → profit_and_loss_period) |
| 5 | `backend/tally_bridge/queries/reports.py` | Bug 7 (profit_and_loss_period subtraction approach) |
| 6 | `frontend/src/components/ChartRenderer.tsx` | Bug 4 (y_keys), Bug 5 (show_legend), Enh 9 (ComposedChart), Enh 11 (formatAxisAmount) |
| 7 | `frontend/src/utils/format.ts` | Enh 11 (formatAxisAmount) |
| 8 | `frontend/src/types/index.ts` | Enh 9 ("composed" in ChartSpec union) |
| 9 | `tests/unit/test_chart_agent.py` | +13 tests |
| 10 | `tests/unit/test_analysis_agent.py` | +7 tests (_extract_chart_title) |
| 11 | `tests/unit/test_pnl_period.py` | +12 tests (new file) |
| 12 | `frontend/src/__tests__/ChartRenderer.test.tsx` | +4 tests |
| 13 | `frontend/src/__tests__/format.test.ts` | +7 tests |
| 14 | `frontend/src/__tests__/fixtures/eval_responses.json` | +2 fixtures (sales_trend_composed, top_customers_ranked) |
| 15-29 | Playwright screenshots | 6 new + 9 updated PNGs |

## Next Verification (Phase 2)

1. ~~Run unit tests~~ ✅ 386 BE + 101 FE passing
2. ~~Run Playwright~~ ✅ 36 tests passing, screenshots visually inspected
3. ~~Rerun eval~~ ✅ run_20260310_154920
4. ~~Run judge~~ ✅ All chart scores = 4, quality 4-5, coherence 5
5. ~~Target: All chart scores ≥ 4~~ ✅ Achieved on turns 2-5

### Eval Run 3 Results (run_20260310_154920) — Post Phase 2+3

| Turn | Query | Table | Chart | Factual | Quality | Coherence | Chart Score |
|------|-------|-------|-------|---------|---------|-----------|-------------|
| 1 | P&L this month | False | False | 3 | 4 | 5 | - |
| 2 | Sales trend FY 25-26 | True | True | 4 | 5 | 5 | 4 |
| 3 | Compare Q2 vs Q3 | True | True | 4 | 5 | 5 | 4 |
| 4 | Top 10 customers | True | True | 4 | 5 | 5 | 4 |
| 5 | Month-wise trend hcode | True | True | 3 | 5 | 5 | 4 |

**Fix applied**: Simplified `generate_followup()` in collect.py — always re-states original query with date context instead of keyword-based redirect that caused Turn 1→trial balance and Turn 5→clarification loop.

**Remaining issues from judge feedback** (addressed in Phase 5 below):
- Change % = 0 in all charts (turns 2, 3, 5) — `_to_numeric` doesn't strip `%`
- Feb 2026 shows -100% in table — should be N/A (no data, not a real decline)
- Chart title says "Jul–Jan" but data includes all 12 months Apr–Mar
- GST base vs invoice confusion: HCODE ₹16.42L (invoice) vs ₹15.70L (base) unexplained
- Langfuse session grouping not working despite `langfuse.session.id` attribute

---

## Phase 5 — Eval Accuracy & Langfuse Session Fixes (DONE — run_20260310_174422)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix chart Change % rendering, GST consistency, trend data trimming, and Langfuse session grouping.

**Architecture:** Backend-only fixes in chart_agent.py (data parsing), analysis_agent.py (prompt + trend trimming), prompts.py (GST instructions), and Langfuse OTLP setup. No frontend changes needed.

### Task 1: Fix `_to_numeric` to Parse Percentage Strings

**Problem:** `_to_numeric("+1.7%")` returns 0.0 because `%` is not stripped. All Change % chart values render as 0.

**Files:**
- Modify: `backend/agents/chart_agent.py:226-236` (`_to_numeric`)
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write failing tests**

```python
# In tests/unit/test_chart_agent.py

def test_to_numeric_percentage_string():
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("+1.7%") == 1.7

def test_to_numeric_negative_percentage():
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("-13.0%") == -13.0

def test_to_numeric_dash():
    """First row of trend data uses '—' for no-prior-period."""
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("—") == 0.0

def test_to_numeric_na():
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("N/A") == 0.0

def test_to_numeric_na_base_zero():
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("N/A (base is zero)") == 0.0

def test_to_numeric_positive_with_plus():
    from backend.agents.chart_agent import _to_numeric
    assert _to_numeric("+100.0%") == 100.0
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::test_to_numeric_percentage_string -v`
Expected: FAIL — `assert 0.0 == 1.7`

- [x] **Step 3: Fix `_to_numeric` to strip `%` before parsing**

```python
def _to_numeric(val: Any) -> float:
    """Coerce a value to float, stripping currency symbols, commas, and %."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("₹", "").replace(",", "").replace("%", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py -v -k "to_numeric"`

- [x] **Step 5: Commit**

### Task 2: Trim Trailing Zero Months from Trend Data

**Problem:** Feb 2026 shows `-100%` change (misleading). Chart data includes all 12 months but title says "Jul–Jan".

**Files:**
- Modify: `backend/agents/chart_agent.py` (new `_trim_trailing_zeros` + wire into `execute`)
- Test: `tests/unit/test_chart_agent.py`

- [x] **Step 1: Write failing tests**

```python
def test_trim_trailing_zeros_removes_empty_tail():
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Jan 2026", 611850, "+270650.00", "+30.7%"],
        ["Feb 2026", 0, "-611850.00", "-100.0%"],
        ["Mar 2026", 0, "+0.00", "N/A"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 1
    assert trimmed[0][0] == "Jan 2026"

def test_trim_trailing_zeros_keeps_mid_zeros():
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Apr 2025", 0, "—", "—"],
        ["May 2025", 100, "+100.00", "N/A"],
        ["Jun 2025", 0, "-100.00", "-100.0%"],
        ["Jul 2025", 200, "+200.00", "N/A"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 4  # mid-sequence zero preserved

def test_trim_trailing_zeros_also_trims_leading():
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Apr 2025", 0, "—", "—"],
        ["May 2025", 0, "+0.00", "N/A"],
        ["Jun 2025", 0, "+0.00", "N/A"],
        ["Jul 2025", 295000, "+295000.00", "N/A"],
        ["Aug 2025", 300000, "+5000.00", "+1.7%"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 2
    assert trimmed[0][0] == "Jul 2025"
```

- [x] **Step 2: Implement `_trim_trailing_zeros`**

```python
def _trim_trailing_zeros(headers: list[str], rows: list[list]) -> list[list]:
    """Remove leading and trailing all-zero rows from trend data."""
    if not rows or len(headers) < 2:
        return rows
    first_nonzero = None
    last_nonzero = None
    for i, row in enumerate(rows):
        val = _to_numeric(row[1]) if len(row) > 1 else 0
        if val != 0:
            if first_nonzero is None:
                first_nonzero = i
            last_nonzero = i
    if first_nonzero is None:
        return rows
    return rows[first_nonzero : last_nonzero + 1]
```

Wire into `execute()` for trend queries only:
```python
if query_type in ("trend",) and rows:
    rows = _trim_trailing_zeros(headers, rows)
```

- [x] **Step 3: Run tests, commit**

### Task 3: Add GST Base-vs-Invoice Clarity to Analysis Prompt

**Problem:** HCODE total ₹16,42,000 (invoice incl. GST) vs ₹15,70,000 (base in Turn 4) — discrepancy unexplained. Inconsistent GST treatment across months.

**Files:**
- Modify: `backend/agents/prompts.py` (`build_analysis_agent_prompt`)
- Test: `tests/unit/test_prompts.py`

- [x] **Step 1: Write test, implement rule #8**

Add to analysis prompt rules:
```
8. **GST / Tax handling**: Tally vouchers may include GST components (CGST, SGST, IGST).
   - Clearly state whether figures are "base value (excl. GST)" or "invoice value (incl. GST)".
   - If GST treatment changed mid-year, note this and reconcile totals.
   - When a customer total differs between analyses, explain: "₹15.70L base + ₹72K GST = ₹16.42L invoiced".
   - Prefer base values for like-for-like comparisons.
```

- [x] **Step 2: Run test, commit**

### Task 4: Handle N/A for Drop-to-Zero Change %

**Problem:** Feb 2026 shows `-100.0%` in table — misleading for months with no data.

**Files:**
- Modify: `backend/agents/analysis_agent.py:310-341` (`_tool_compute_trend`)
- Test: `tests/unit/test_analysis_agent.py`

- [x] **Step 1: Write failing test**

```python
def test_compute_trend_trailing_zero_shows_na():
    from backend.agents.analysis_agent import _tool_compute_trend
    series = [
        {"period": "Jan 2026", "value": 611850},
        {"period": "Feb 2026", "value": 0},
        {"period": "Mar 2026", "value": 0},
    ]
    result = _tool_compute_trend(series)
    rows = result["rows"]
    assert rows[1][3] == "N/A"  # not "-100.0%"
    assert rows[2][3] == "N/A"  # 0→0 also N/A
```

- [x] **Step 2: Fix `_tool_compute_trend`** — when value drops to 0, show N/A not -100%

```python
if value == 0 and prev != 0:
    pct_chg = None
    pct_str = "N/A"
elif prev == 0:
    pct_chg = None
    pct_str = "N/A"
else:
    pct_chg = ((abs_chg / abs(prev)) * 100)
    pct_str = f"{pct_chg:+.1f}%"
```

- [x] **Step 3: Run tests, commit**

### Task 5: Debug and Fix Langfuse Session Grouping

**Problem:** `langfuse.session.id` span attribute added (commit 02f2f1b) but sessions not grouped in Langfuse dashboard.

**Files:**
- Modify: `scripts/test_langfuse.py` (add session test with 2 API calls)
- Modify: `backend/main.py` (possibly add BaggageSpanProcessor)
- Modify: `backend/api/chat.py` (possibly switch to baggage-based propagation)
- Modify: `pyproject.toml` (possibly add `opentelemetry-processor-baggage`)

- [x] **Step 1: Enhance test script** — 2 API calls under same session_id, flush, check dashboard
- [x] **Step 2: Debug** — likely need `BaggageSpanProcessor(ALLOW_ALL_BAGGAGE_KEYS)` so child spans inherit session_id
- [x] **Step 3: Fix and re-test**
- [x] **Step 4: Commit**

### Task 6: Run Full Test Suite + Eval Verification

- [x] **Step 1:** `ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest tests/unit/ tests/integration/ tests/e2e/ -v`
- [x] **Step 2:** `cd frontend && npm test`
- [x] **Step 3:** Rerun eval collect → judge → report
- [x] **Step 4:** Target: Chart ≥ 4, Factual ≥ 4 on turns 2-5, no -100% for empty months
- [x] **Step 5:** Update plan and memory, final commit

### Phase 5 Summary of Changes

| # | File | Change |
|---|------|--------|
| 1 | `backend/agents/chart_agent.py` | `_to_numeric` strips `%`; new `_trim_trailing_zeros`; wire into `execute()` |
| 2 | `backend/agents/analysis_agent.py` | `_tool_compute_trend` returns N/A for drops-to-zero |
| 3 | `backend/agents/prompts.py` | GST base-vs-invoice rule #8 in analysis prompt |
| 4 | `tests/unit/test_chart_agent.py` | +10 tests (_to_numeric, _trim_trailing_zeros) |
| 5 | `tests/unit/test_analysis_agent.py` | +1 test (trend trailing zero) |
| 6 | `tests/unit/test_prompts.py` | +1 test (GST rule presence) |
| 7 | `scripts/test_langfuse.py` | Enhanced: session grouping test with 2 API calls |
| 8 | `backend/api/chat.py` | Explicit root span with `langfuse.session.id` attribute (was no-op span) |

### Phase 5 Eval Results (run_20260310_174422)

| Turn | Query | Table | Chart | Factual | Quality | Coherence | Chart Score |
|------|-------|-------|-------|---------|---------|-----------|-------------|
| 1 | P&L this month | False | False | 3 | 4 | 5 | - |
| 2 | Sales trend FY 25-26 | True | True | 4 | 5 | 5 | **5** |
| 3 | Compare Q2 vs Q3 | True | True | 4 | 5 | 5 | 4 |
| 4 | Top 10 customers | True | True | 4 | 5 | 5 | 4 |
| 5 | Month-wise trend hcode | True | False | 3 | 4 | 5 | - |

**Improvements vs Phase 2 run**: Turn 2 chart 4→5 (Change % line renders correctly, trailing zeros trimmed, N/A for empty months). All coherence 5/5.

**Remaining**: Turn 5 clarification loop + aggregate-only data (model-level issue, Phase 4 candidate). Turn 1 factual=3 (zero balances can't be verified).

---

## Phase 6 — Tool Call Optimization & Data Accuracy Fixes (DONE — commit 8cc44ad)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Tally date filtering, reduce tool calls from 12→1-2 per trend query, fix clarification false positives, preserve trend table data, add totals rows, fix screenshot clipping, add judge totals verification.

**Root causes identified from be_run4.log analysis (run_20260310_174422):**

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | Turn 2: 12 redundant get_sales_register calls | `_wrap_voucher_collection` has no TDL date filter — Tally ignores SVFROMDATE/SVTODATE for TYPE=Collection | Add TDL `DateRangeFilter` + Python-side fallback |
| 2 | Turn 2: Model computes wrong Dec totals (682K/782K vs correct 882K) | No month field in voucher data; model does manual arithmetic | Add `month` field to parsed vouchers + prompt: "fetch full range, use compute_totals group_by" |
| 3 | Turn 5: False clarification detection | Keyword `"which"` matches analytical prose ("which could indicate") | Tighten keywords + structured-data guard |
| 4 | Turn 5: Followup returns 1-row aggregate instead of 12-row trend | `last_table_data` overwritten by `compute_totals` after `compute_trend` | Add `trend_table_data` tracker (like `ranked_table_data`) |
| 5 | Turns 3/4: Missing totals row in tables | Agent mentions totals in prose but not in structured headers/rows data | Add prompt rule + `_ensure_totals_row` post-processing fallback |
| 6 | Turn 3: Change/Change% columns clipped in screenshot | `overflow-x-auto` + `table_el.screenshot()` captures only visible width | Remove overflow clipping before screenshot |

### Task 1: TDL Date Filter for Voucher Collections

**Files**: `backend/tally_bridge/request_builder.py`, `backend/tally_bridge/response_parser.py`, `backend/tally_bridge/queries/vouchers.py`, `tests/unit/test_request_builder.py`

**Approach**: Add `DateRangeFilter` to `_wrap_voucher_collection()` using Tally's `$$InDateRange` TDL function (existing `VchTypeFilter` pattern). Plus Python-side date filtering in `parse_vouchers()` as safety net.

- [x] **Step 1**: Write failing tests — verify XML output contains DateRangeFilter
```python
def test_voucher_collection_has_date_filter():
    xml = build_sales_register("01-07-2025", "31-07-2025")
    assert "DateRangeFilter" in xml
    assert "InDateRange" in xml
```

- [x] **Step 2**: Add DateRangeFilter to `_wrap_voucher_collection()`:
```python
# Always add date filter
date_filter = "<FILTER>DateRangeFilter</FILTER>"
date_system = f'<SYSTEM TYPE="Formulae" NAME="DateRangeFilter">$$InDateRange:$Date:{from_date}:{to_date}</SYSTEM>'
# Combine with VchTypeFilter if present
```

- [x] **Step 3**: Add Python-side date filtering as safety net in `parse_vouchers()`:
```python
def parse_vouchers(raw_xml: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    ...
    if from_date and to_date:
        vouchers = _filter_by_date(vouchers, from_date, to_date)
    return vouchers
```
Thread `from_date`/`to_date` from query functions through to `parse_vouchers`.

- [x] **Step 4**: Run tests — `pytest tests/unit/test_request_builder.py -v`

**Note**: `$$InDateRange` uses DD-MM-YYYY format matching our convention. Fallback: `$Date >= "{from_date}" AND $Date <= "{to_date}"`.

### Task 2: Add `month` Field to Parsed Vouchers + Prompt Optimization

**Files**: `backend/tally_bridge/response_parser.py`, `backend/agents/prompts.py`, `tests/unit/test_response_parser.py`

- [x] **Step 1**: Add `month` field extraction in `parse_vouchers()`:
```python
if date_str and len(date_str) == 8:
    dt = datetime.strptime(date_str, "%Y%m%d")
    month_str = dt.strftime("%b %Y")  # "Dec 2025"
else:
    month_str = ""
vouchers.append({..., "month": month_str})
```

- [x] **Step 2**: Add prompt rule to QueryAgent (`build_query_agent_prompt`):
```
11. For trend/time-series queries, fetch the FULL date range in ONE call, then use
    compute_totals with group_by to aggregate by month/quarter. Do NOT make separate
    calls per period — the data includes a 'month' field for grouping.
```

- [x] **Step 3**: Write tests, run `pytest tests/unit/test_response_parser.py -v`

### Task 3: Fix Clarification Detection in Eval Collector

**File**: `tests/eval/collect.py`

- [x] **Step 1**: Tighten keyword matching + add structured-data guard:
```python
clarification_keywords = ["specify", "clarif", "could you provide", "what type", "more specific", "which one"]

# Only treat as clarification if response has NO structured data
if not response.get("has_table") and not response.get("has_chart"):
    if any(kw in msg_lower for kw in clarification_keywords):
        is_clarification = True
```

Key changes:
- Remove bare `"which"` → replace with `"which one"` (more specific)
- Remove bare `"could you"` → replace with `"could you provide"`
- Add guard: if response has table/chart, it's NOT a clarification

- [x] **Step 2**: Test with Turn 5's original response to confirm no false positive

### Task 4: Add `trend_table_data` Tracker in Analysis Agent

**File**: `backend/agents/analysis_agent.py`, `tests/unit/test_analysis_agent.py`

Follow exact pattern of `ranked_table_data` for top_n:

- [x] **Step 1**: Add `trend_table_data: dict | None = None` initialization (after line 420)

- [x] **Step 2**: Capture compute_trend results separately (after line 486):
```python
if tool_block.name == "compute_trend":
    trend_table_data = {"headers": d["headers"], "rows": d["rows"]}
```

- [x] **Step 3**: Update all 3 `preferred_data` selection points:
```python
preferred_data = (
    trend_table_data if (query_type == "trend" and trend_table_data)
    else ranked_table_data if (query_type == "top_n" and ranked_table_data)
    else last_table_data
)
```

- [x] **Step 4**: Write failing test, verify fix

### Task 5: Add Totals Row to Analysis Tables

**Files**: `backend/agents/prompts.py`, `backend/agents/analysis_agent.py`

- [x] **Step 1**: Add prompt rule #9 to analysis agent:
```
9. **Summary totals**: Always include a "Total" or "Grand Total" row at the bottom of
   comparison and ranking tables. For trend tables, include a "Total" or "Average" row.
   Format: same columns, first column = "Total", numeric columns = sum.
```

- [x] **Step 2**: Add `_ensure_totals_row()` post-processing fallback:
```python
def _ensure_totals_row(headers: list[str], rows: list[list], query_type: str) -> list[list]:
    if not rows or query_type not in ("comparison", "top_n", "aggregation"):
        return rows
    last_label = str(rows[-1][0]).lower() if rows else ""
    if "total" in last_label or "grand" in last_label:
        return rows
    totals = ["Total"]
    for col_idx in range(1, len(headers)):
        col_vals = [_to_numeric_safe(row[col_idx]) for row in rows if col_idx < len(row)]
        totals.append(sum(col_vals))
    rows.append(totals)
    return rows
```

- [x] **Step 3**: Write tests, verify

### Task 6: Fix Table Screenshot Width Clipping

**File**: `tests/eval/collect.py`

- [x] **Step 1**: Before taking table screenshot, remove overflow clipping:
```python
table_container = last_msg.locator(".overflow-x-auto")
if await table_container.count() > 0:
    await table_container.first.evaluate("el => el.style.overflow = 'visible'")
```

- [x] **Step 2**: Verify Turn 3 screenshot shows all 5 columns

### Task 7: Add Explicit Totals Check to Eval Judge

**Files**: `tests/eval/judge.py`, `tests/eval/prompts.py`

- [x] **Step 1**: Add to judge prompt checks for comparison/top_n/trend turns:
```
- Verify a "Total" or "Grand Total" row exists in the data table
- Verify the total is arithmetically correct (sum of individual rows)
- Compare the total against ground truth if available (e.g., trial balance, P&L totals)
```

- [x] **Step 2**: Add explicit checks in scenario definition for turns with totals:
  - Turn 2 (sales trend): Total sales should match FY total from trial balance
  - Turn 3 (Q2 vs Q3): Column totals should match quarter P&L figures
  - Turn 4 (top customers): Grand total should match total sales from Turn 2

- [x] **Step 3**: Update judge scoring rubric — factual score penalized if totals row missing or doesn't match ground truth

### Task 8: Run Full Test Suite + Eval Verification

- [x] **Step 1**: `ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest tests/unit/ tests/integration/ tests/e2e/ -v`
- [x] **Step 2**: `cd frontend && npm test -- --run`
- [x] **Step 3**: Rerun eval collect → judge → report
- [x] **Step 4**: Verify all acceptance criteria below

### Phase 6 Acceptance Criteria

1. **Turn 2**: 1-2 Tally calls (not 12), model uses compute_totals, Dec 2025 total correct, totals row present and matches ground truth
2. **Turn 3**: Tables include "Total" row, all 5 columns visible in screenshot, totals match quarter P&L
3. **Turn 4**: "Total" row present, grand total matches FY sales
4. **Turn 5**: No false clarification, full 7+ row trend table (not 1-row aggregate), chart renders
5. **Judge**: Explicit totals check passes — total row exists, arithmetic correct, matches ground truth
6. **All tests pass**: Backend 459+, Frontend 101+

### Phase 6 Files Modified (Expected)

| # | File | Changes |
|---|------|---------|
| 1 | `backend/tally_bridge/request_builder.py` | TDL DateRangeFilter in `_wrap_voucher_collection` |
| 2 | `backend/tally_bridge/response_parser.py` | `month` field extraction + Python date filtering in `parse_vouchers` |
| 3 | `backend/tally_bridge/queries/vouchers.py` | Thread from_date/to_date to parse_vouchers |
| 4 | `backend/agents/prompts.py` | Rule #11 (one-call trend), Rule #9 (totals row) |
| 5 | `backend/agents/analysis_agent.py` | `trend_table_data` tracker + `_ensure_totals_row` |
| 6 | `tests/eval/collect.py` | Clarification detection fix + screenshot overflow fix |
| 7 | `tests/eval/judge.py` | Explicit totals check in judge prompt |
| 8 | `tests/eval/prompts.py` | Judge prompt totals verification rules |
| 9 | `tests/unit/test_request_builder.py` | +3 tests (date filter) |
| 10 | `tests/unit/test_response_parser.py` | +3 tests (month field, date filtering) |
| 11 | `tests/unit/test_analysis_agent.py` | +7 tests (_ensure_totals_row) |

### Phase 6 Implementation Summary (commit 8cc44ad)

All 8 tasks implemented. 11 files changed, +330/-18 lines.

| Suite | Count | Delta |
|-------|-------|-------|
| Backend unit+integration+e2e | 477 | +18 |
| Frontend Vitest | 101 | +0 |
| **Total** | **578** | **+18** |

**Note**: Totals verification in judge was added to `rubrics.py` (not `judge.py`/`prompts.py` as originally planned) since that's where `build_judge_prompt` lives. New `_should_verify_totals()` helper + `TOTALS_VERIFICATION_INSTRUCTIONS` constant in rubrics.py.

**Pending**: Eval collect → judge → report run to verify acceptance criteria (scheduled for next session).

---

## Phase 7 — Date Format Validation & Ledger Voucher DateRangeFilter

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent bad date formats from reaching Tally (which crashes it), add DateRangeFilter to `build_ledger_vouchers()`, and add comprehensive bridge-level tests.

**Architecture:** Add a `validate_tally_date()` function in date_utils.py, wire it into `execute_tool()` as a pre-flight check on all date parameters, fix `build_ledger_vouchers()` to include TDL DateRangeFilter (matching `_wrap_voucher_collection` pattern), and add tests covering invalid formats, full FY ranges, and the ledger voucher gap.

**Root causes from eval run_20260311_104350:**

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | Bad date format crashes Tally | No validation — Claude can pass YYYY-MM-DD, ISO, or garbage strings directly into XML | Add `validate_tally_date()` + pre-flight check in `execute_tool()` |
| 2 | `build_ledger_vouchers()` ignores date range | Missing DateRangeFilter TDL — only has SVFROMDATE/SVTODATE which Tally ignores for TYPE=Collection | Add DateRangeFilter + LedgerFilter (both filters in same query) |

### Task 1: Add `validate_tally_date()` to date_utils.py

**Files:**
- Modify: `backend/utils/date_utils.py`
- Test: `tests/unit/test_date_utils.py`

- [x] **Step 1: Write failing tests**

```python
# In tests/unit/test_date_utils.py

from backend.utils.date_utils import validate_tally_date

class TestValidateTallyDate:
    def test_valid_date(self):
        assert validate_tally_date("01-04-2025") == "01-04-2025"

    def test_valid_date_end_of_month(self):
        assert validate_tally_date("31-03-2026") == "31-03-2026"

    def test_valid_date_leap_year(self):
        assert validate_tally_date("29-02-2028") == "29-02-2028"

    def test_iso_format_rejected(self):
        """YYYY-MM-DD is NOT valid Tally format."""
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("2025-04-01")

    def test_slash_format_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("01/04/2025")

    def test_garbage_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("not-a-date")

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("")

    def test_invalid_day_rejected(self):
        """Feb 30 doesn't exist."""
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("30-02-2025")

    def test_iso_autofix(self):
        """YYYY-MM-DD auto-converted to DD-MM-YYYY."""
        assert validate_tally_date("2025-04-01", autofix=True) == "01-04-2025"

    def test_iso_autofix_validates_result(self):
        """Auto-fixed date must also be a valid calendar date."""
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("2025-13-01", autofix=True)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_date_utils.py::TestValidateTallyDate -v`
Expected: FAIL — `ImportError: cannot import name 'validate_tally_date'`

- [x] **Step 3: Implement `validate_tally_date`**

Add to `backend/utils/date_utils.py`:

```python
import re
from datetime import datetime

_TALLY_DATE_RE = re.compile(r'^\d{2}-\d{2}-\d{4}$')
_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def validate_tally_date(date_str: str, autofix: bool = False) -> str:
    """Validate a date string is in DD-MM-YYYY format.

    Args:
        date_str: Date string to validate.
        autofix: If True, attempt to convert YYYY-MM-DD to DD-MM-YYYY.

    Returns:
        Validated DD-MM-YYYY string.

    Raises:
        ValueError: If date_str is not valid DD-MM-YYYY format.
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError(f"Invalid date '{date_str}': expected DD-MM-YYYY format")

    s = date_str.strip()

    # Auto-fix ISO format (YYYY-MM-DD → DD-MM-YYYY)
    if autofix and _ISO_DATE_RE.match(s):
        parts = s.split("-")
        s = f"{parts[2]}-{parts[1]}-{parts[0]}"

    if not _TALLY_DATE_RE.match(s):
        raise ValueError(f"Invalid date '{date_str}': expected DD-MM-YYYY format")

    # Validate it's a real calendar date
    try:
        datetime.strptime(s, "%d-%m-%Y")
    except ValueError:
        raise ValueError(f"Invalid date '{date_str}': expected DD-MM-YYYY format")

    return s
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_date_utils.py::TestValidateTallyDate -v`
Expected: PASS (all 11 tests)

- [x] **Step 5: Commit**

```bash
git add backend/utils/date_utils.py tests/unit/test_date_utils.py
git commit -m "feat: add validate_tally_date() with autofix for ISO dates"
```

### Task 2: Wire Date Validation into `execute_tool()` + Tool Handler Tests

**Files:**
- Modify: `backend/agents/tools.py`
- Test: `tests/unit/test_tools.py`

**Note on scope:** `execute_tool()` is the SOLE gateway for all Claude→Tally tool calls (confirmed by tracing `query_agent.py` line 145). Validating here catches all bad dates before they reach any request builder. The direct API route (`GET /api/reports/{name}`) bypasses this — lower priority since it's not used by the agent pipeline.

- [x] **Step 1: Write failing tests**

```python
# In tests/unit/test_tools.py

import pytest
from unittest.mock import AsyncMock, patch
from backend.agents.tools import execute_tool

# --- Date validation tests ---

@pytest.mark.asyncio
async def test_execute_tool_rejects_garbage_from_date():
    """Garbage date string must be rejected before reaching Tally."""
    client = AsyncMock()
    result = await execute_tool(client, "get_day_book", {
        "from_date": "garbage", "to_date": "31-03-2026"
    })
    assert "error" in result
    assert "DD-MM-YYYY" in result["error"]
    client.post_xml.assert_not_called()  # Must NOT reach Tally

@pytest.mark.asyncio
async def test_execute_tool_rejects_garbage_to_date():
    """Bad to_date also rejected."""
    client = AsyncMock()
    result = await execute_tool(client, "get_trial_balance", {
        "from_date": "01-04-2025", "to_date": "not-a-date"
    })
    assert "error" in result
    assert "DD-MM-YYYY" in result["error"]

@pytest.mark.asyncio
async def test_execute_tool_rejects_garbage_as_on_date():
    """as_on_date param validated too."""
    client = AsyncMock()
    result = await execute_tool(client, "get_balance_sheet", {
        "as_on_date": "31/03/2026"
    })
    assert "error" in result
    assert "DD-MM-YYYY" in result["error"]

@pytest.mark.asyncio
async def test_execute_tool_autofixes_iso_from_date():
    """ISO YYYY-MM-DD auto-converted to DD-MM-YYYY before calling handler."""
    client = AsyncMock()
    with patch("backend.agents.tools._handle_trial_balance", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = {"report_name": "Trial Balance", "rows": []}
        result = await execute_tool(client, "get_trial_balance", {
            "from_date": "2025-04-01", "to_date": "2026-03-31"
        })
    # Handler should have received corrected DD-MM-YYYY dates
    call_kwargs = mock_handler.call_args
    assert call_kwargs is not None
    _, kwargs = call_kwargs
    assert kwargs["from_date"] == "01-04-2025"
    assert kwargs["to_date"] == "31-03-2026"

@pytest.mark.asyncio
async def test_execute_tool_autofixes_iso_as_on_date():
    """ISO as_on_date also auto-converted."""
    client = AsyncMock()
    with patch("backend.agents.tools._handle_balance_sheet", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = {"report_name": "Balance Sheet", "rows": []}
        result = await execute_tool(client, "get_balance_sheet", {
            "as_on_date": "2026-03-31"
        })
    _, kwargs = mock_handler.call_args
    assert kwargs["as_on_date"] == "31-03-2026"

@pytest.mark.asyncio
async def test_execute_tool_valid_dates_pass_through():
    """Valid DD-MM-YYYY dates pass through unchanged."""
    client = AsyncMock()
    with patch("backend.agents.tools._handle_sales_register", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = []
        result = await execute_tool(client, "get_sales_register", {
            "from_date": "01-04-2025", "to_date": "31-03-2026"
        })
    _, kwargs = mock_handler.call_args
    assert kwargs["from_date"] == "01-04-2025"
    assert kwargs["to_date"] == "31-03-2026"

@pytest.mark.asyncio
async def test_execute_tool_no_dates_skips_validation():
    """Tools without date params (list_companies, search_ledger) skip validation."""
    client = AsyncMock()
    with patch("backend.agents.tools._handle_list_companies", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = [{"name": "Test Co"}]
        result = await execute_tool(client, "list_companies", {})
    assert "error" not in result
    mock_handler.assert_called_once()

# --- Tool handler routing tests ---

@pytest.mark.asyncio
async def test_execute_tool_unknown_tool():
    """Unknown tool name returns error."""
    client = AsyncMock()
    result = await execute_tool(client, "nonexistent_tool", {})
    assert "error" in result
    assert "Unknown tool" in result["error"]

@pytest.mark.asyncio
async def test_execute_tool_tally_connection_error():
    """TallyConnectionError is caught and returned as error dict."""
    from backend.tally_bridge.exceptions import TallyConnectionError
    client = AsyncMock()
    with patch("backend.agents.tools._handle_trial_balance", new_callable=AsyncMock) as mock_handler:
        mock_handler.side_effect = TallyConnectionError("Tally unreachable")
        result = await execute_tool(client, "get_trial_balance", {
            "from_date": "01-04-2025", "to_date": "31-03-2026"
        })
    assert "error" in result
    assert "unreachable" in result["error"]

@pytest.mark.asyncio
async def test_execute_tool_success_wraps_data():
    """Successful tool call wraps result in {success: True, data: ...}."""
    client = AsyncMock()
    with patch("backend.agents.tools._handle_search_ledger", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = [{"name": "Cash", "parent": "Cash-in-Hand"}]
        result = await execute_tool(client, "search_ledger", {"search_term": "cash"})
    assert result["success"] is True
    assert result["data"] == [{"name": "Cash", "parent": "Cash-in-Hand"}]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tools.py -v`
Expected: FAIL — no validation exists yet (date tests fail), handler routing tests may pass

- [x] **Step 3: Add date validation to `execute_tool()`**

In `backend/agents/tools.py`, add pre-flight validation:

```python
from backend.utils.date_utils import validate_tally_date

# Date parameter names across all tools
_DATE_PARAMS = {"from_date", "to_date", "as_on_date"}


async def execute_tool(
    client: TallyClient,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name!r}"}

    # Validate and autofix date parameters
    for param in _DATE_PARAMS:
        if param in tool_input:
            try:
                tool_input[param] = validate_tally_date(tool_input[param], autofix=True)
            except ValueError as exc:
                return {"error": str(exc)}

    try:
        result = await handler(client, **tool_input)
        return {"success": True, "data": result}
    except TallyConnectionError as exc:
        return {"error": str(exc)}
    except TallyResponseError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected error in tool %r", tool_name)
        return {"error": f"Unexpected error in {tool_name!r}: {exc}"}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_tools.py -v`
Expected: PASS (all 11 tests)

- [x] **Step 5: Commit**

```bash
git add backend/agents/tools.py tests/unit/test_tools.py
git commit -m "feat: validate date params in execute_tool with ISO autofix + tool handler tests"
```

### Task 3: Add DateRangeFilter to `build_ledger_vouchers()`

**Files:**
- Modify: `backend/tally_bridge/request_builder.py`
- Test: `tests/unit/test_request_builder.py`

- [x] **Step 1: Write failing tests**

```python
# Add to tests/unit/test_request_builder.py, in class TestDateRangeFilter

def test_ledger_vouchers_has_date_filter(self):
    xml = build_ledger_vouchers("Cash", "01-07-2025", "31-07-2025")
    assert "DateRangeFilter" in xml
    assert "$$InDateRange:$Date:01-07-2025:31-07-2025" in xml

def test_ledger_vouchers_has_both_filters(self):
    """Ledger vouchers need both DateRangeFilter AND LedgerFilter."""
    xml = build_ledger_vouchers("HDFC Bank", "01-04-2025", "31-03-2026")
    assert "DateRangeFilter" in xml
    assert "LedgerFilter" in xml
    assert "$$InDateRange" in xml
    assert "HDFC Bank" in xml

def test_ledger_vouchers_full_fy_range(self):
    """Full FY query should work — dates in correct DD-MM-YYYY format."""
    xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
    assert "$$InDateRange:$Date:01-04-2025:31-03-2026" in xml
    assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
    assert "<SVTODATE>31-03-2026</SVTODATE>" in xml
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_request_builder.py::TestDateRangeFilter -v`
Expected: FAIL — `assert "DateRangeFilter" in xml` for ledger vouchers

- [x] **Step 3: Fix `build_ledger_vouchers()` to include DateRangeFilter**

Replace the function in `backend/tally_bridge/request_builder.py`:

```python
def build_ledger_vouchers(ledger_name: str, from_date: str, to_date: str, company: str | None = None) -> str:
    """Fetch vouchers for a specific ledger using TDL Collection with filters.
    Uses $PartyLedgerName comparison instead of $$IsLedgerInVoucher because
    the latter cannot handle ledger names containing commas.
    Includes DateRangeFilter because Tally ignores SVFROMDATE/SVTODATE for TYPE=Collection.
    """
    company_var = f"<SVCurrentCompany>{company}</SVCurrentCompany>" if company else ""
    safe_name = xml_escape(ledger_name, {'"': "&quot;"})
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>LedgerVchs</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
{company_var}
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="LedgerVchs" ISMODIFY="No">
<TYPE>Voucher</TYPE>
<FILTER>DateRangeFilter</FILTER>
<FILTER>LedgerFilter</FILTER>
{_voucher_native_methods()}
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="DateRangeFilter">$$InDateRange:$Date:{from_date}:{to_date}</SYSTEM>
<SYSTEM TYPE="Formulae" NAME="LedgerFilter">$PartyLedgerName = "{safe_name}"</SYSTEM>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_request_builder.py::TestDateRangeFilter -v`
Expected: PASS (all existing + 3 new tests)

- [x] **Step 5: Commit**

```bash
git add backend/tally_bridge/request_builder.py tests/unit/test_request_builder.py
git commit -m "fix: add DateRangeFilter to build_ledger_vouchers (Tally ignores SVFROMDATE for Collection)"
```

### Task 4: Add Bridge-Level Tests for Full FY Date Ranges

**Files:**
- Test: `tests/unit/test_request_builder.py`

- [x] **Step 1: Write tests for all builders with full FY range**

```python
# Add new class to tests/unit/test_request_builder.py

class TestFullFYDateRange:
    """Verify all report/voucher builders handle full FY date ranges correctly."""

    def test_trial_balance_full_fy(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_profit_and_loss_full_fy(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_sales_register_full_fy(self):
        xml = build_sales_register("01-04-2025", "31-03-2026")
        assert "$$InDateRange:$Date:01-04-2025:31-03-2026" in xml
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_purchase_register_full_fy(self):
        xml = build_purchase_register("01-04-2025", "31-03-2026")
        assert "$$InDateRange:$Date:01-04-2025:31-03-2026" in xml

    def test_day_book_full_fy(self):
        xml = build_day_book("01-04-2025", "31-03-2026")
        assert "$$InDateRange:$Date:01-04-2025:31-03-2026" in xml

    def test_ledger_vouchers_full_fy(self):
        xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
        assert "$$InDateRange:$Date:01-04-2025:31-03-2026" in xml

    def test_balance_sheet_single_date(self):
        xml = build_balance_sheet("31-03-2026")
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml
```

- [x] **Step 2: Run tests**

Run: `pytest tests/unit/test_request_builder.py::TestFullFYDateRange -v`
Expected: PASS (all 7 tests — Task 3 must be done first for ledger_vouchers)

- [x] **Step 3: Commit**

```bash
git add tests/unit/test_request_builder.py
git commit -m "test: add full FY date range tests for all request builders"
```

### Task 5: Run Full Test Suite

- [x] **Step 1:** `ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest tests/unit/ tests/integration/ tests/e2e/ -v`
- [x] **Step 2:** Verify no regressions — all existing 477 BE tests pass + new tests
- [x] **Step 3:** Final commit if needed

### Phase 7 Files Modified (Expected)

| # | File | Changes |
|---|------|---------|
| 1 | `backend/utils/date_utils.py` | New `validate_tally_date()` with autofix |
| 2 | `backend/agents/tools.py` | Date validation in `execute_tool()` pre-flight |
| 3 | `backend/tally_bridge/request_builder.py` | DateRangeFilter added to `build_ledger_vouchers()` |
| 4 | `tests/unit/test_date_utils.py` | +11 tests (validate_tally_date) |
| 5 | `tests/unit/test_tools.py` | +11 tests (date validation, autofix, handler routing, error handling) |
| 6 | `tests/unit/test_request_builder.py` | +10 tests (ledger DateRangeFilter + full FY range) |

### Phase 7 Acceptance Criteria

1. `validate_tally_date("2025-04-01")` raises ValueError (ISO format rejected)
2. `validate_tally_date("2025-04-01", autofix=True)` returns `"01-04-2025"`
3. `validate_tally_date("garbage")` raises ValueError
4. `execute_tool(client, "get_trial_balance", {"from_date": "2025-04-01", ...})` auto-fixes ISO→DD-MM-YYYY before calling handler
5. `execute_tool(client, "get_day_book", {"from_date": "garbage", ...})` returns `{"error": "..."}` and does NOT call Tally
6. `execute_tool(client, "get_balance_sheet", {"as_on_date": "2026-03-31"})` auto-fixes as_on_date too
7. `execute_tool` with TallyConnectionError returns error dict (not exception)
8. `build_ledger_vouchers("Cash", ...)` XML contains `DateRangeFilter` and `$$InDateRange`
9. All builders produce correct XML for full FY range `01-04-2025` to `31-03-2026`
10. All tests pass: 477+ BE existing + ~32 new = 509+ total

### Phase 7 Implementation Summary

All tasks implemented across 8 commits. Code review fixes applied (no-mutation shallow copy, end-to-end crash scenario tests).

**Critical fix (commit 9e77cd2):** `$$InDateRange` is NOT a valid TallyPrime TDL function — it crashed Tally with "Cannot understand. Bad Formula!" error. This was introduced in Phase 6's `_wrap_voucher_collection()` and `build_ledger_vouchers()`. **Removed entirely.** Date filtering now relies on:
1. `SVFROMDATE`/`SVTODATE` in STATICVARIABLES (first-pass, may be ignored by Tally for TYPE=Collection)
2. Python-side `_filter_vouchers_by_date()` in `response_parser.py` (reliable safety net, called by all 4 voucher query functions)

| Suite | Count | Delta |
|-------|-------|-------|
| Backend unit+integration+e2e | 512 | +35 |
| Frontend Vitest | 101 | +0 |
| **Total** | **613** | **+35** |

**Live Tally tests**: 4 tests in `tests/e2e_live/test_live_pipeline.py` — all passing:
- `test_live_date_validation_iso_autofix` — ISO date through execute_tool → Tally responds
- `test_live_date_validation_garbage_rejected` — garbage date rejected before reaching Tally
- `test_live_date_validation_full_fy_sales_register` — full FY sales register works
- `test_live_ledger_vouchers_date_filter` — ledger vouchers with LedgerFilter (no DateRangeFilter)

**Status**: All live Tally tests pass. Ready for eval run.

### Note: Direct API Route

`GET /api/reports/{name}` in `backend/api/reports.py` bypasses `execute_tool()`, but it's unused — the frontend and agent pipeline never call it. It's a standalone REST endpoint from Phase 3 for manual `curl` testing (future: direct FE reports fetch). Not in scope for Phase 7.

### Phase 7 Eval Results (run_20260311_134758)

| Turn | Query | Table | Chart | Factual | Quality | Coherence | Chart Score |
|------|-------|-------|-------|---------|---------|-----------|-------------|
| 1 | P&L this month | False | False | 3 | 4 | 5 | - |
| 2 | Sales trend FY 25-26 | True | True | 3 | 5 | 4 | 5 |
| 3 | Compare Q2 vs Q3 | True | True | 3 | 4 | 5 | 3 |
| 4 | Top 10 customers | True | True | 4 | 5 | 5 | 4 |
| 5 | HCODE trend | True | True | 3 | 5 | 5 | 5 |

**Key win**: Turn 5 fully fixed (was clarification loop → now full trend table + composed chart 5/5).
**Regressions**: Turn 3 chart 4→3 (chart grouping issues).

---

## Phase 8 — Eval Accuracy Fixes (Structured Data & Prompts)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 issues from eval run_20260311_134758 + 3 UX improvements — restore trend totals stripped by our pipeline, exclude Total from charts, fix analysis agent hallucinations (ledger names, chart titles, manual computation), explain missing months, strip chart metadata from messages, render markdown tables inline (Langfuse-style), full message screenshots in eval.

**Architecture:** The model output is correct (Langfuse confirms Total rows in markdown), but our structured data pipeline strips them. Changes: analysis_agent.py (restore trend totals), chart_agent.py (filter Total from chart data), prompts.py (analysis agent rules for ledger names, chart titles, tool-only computation, missing months). Agent architecture refactor (QueryAgent vs AnalysisAgent overlap) is **parked for Phase 4** — requires deeper design work.

**Root causes identified from run_20260311_134758 + be_run6.log + Langfuse analysis:**

| # | Issue | Turns | Root Cause | Fix |
|---|-------|-------|-----------|-----|
| 1 | Missing totals in trend tables | 2, 5 | Model output has Total row (confirmed in Langfuse markdown), but structured `data.rows` from `compute_trend` tool doesn't include it. `_ensure_totals_row()` skips `trend` (line 546), so it's never added back. Pipeline strips what the model correctly produced. | Add `"trend"` to `_ensure_totals_row` allowed types |
| 2 | Total bar rendered in chart | 4 | `_ensure_totals_row` adds Total to structured data (correct for tables). `_format_xy_data` then includes it as a chart data point — misleading "Total" bar alongside individual items. | Filter Total/Grand Total rows from chart data only |
| 3 | Turn 3: hallucinated ledger + wrong chart title + manual computation | 3 | Three analysis agent issues: (a) fabricated "SALES EXPORT (Dubai)" from voucher narration "Amit Jain (Dubai)" — only 3 real ledgers exist; (b) chart title "Gross Profit & Net Profit" doesn't match sales-only data; (c) model manually computed per-ledger breakdowns (8,95,000 vs 11,95,000) instead of using tools — only called compute_totals for the final aggregate | Add 3 prompt rules to analysis agent: exact ledger names, chart title accuracy, tool-only computation |
| 4 | Missing months not explained | 2 | `_trim_trailing_zeros` removes Apr-Jun 2025 (no data), model doesn't explain their absence to user | Add prompt rule: explain data gaps |

**Parked for Phase 4 (architectural):** QueryAgent and AnalysisAgent have overlapping ANALYSIS_TOOLS — QueryAgent computes (3-4 calls), then AnalysisAgent re-computes (2-3 calls). This causes Turn 3's 75s latency and text/table total mismatch (11,95,000 in QueryAgent vs 8,95,000 in AnalysisAgent). Requires deeper redesign of agent responsibilities and tool routing. May coincide with model change decision.

### Task 1: Restore Trend Totals in Structured Data

**Files:**
- Modify: `backend/agents/analysis_agent.py:544-546`
- Test: `tests/unit/test_analysis_agent.py`

**Problem:** Model correctly includes Total row in its markdown output (confirmed via Langfuse screenshot). But `compute_trend` tool returns headers/rows without a Total. `_ensure_totals_row()` at line 546 has a guard: `query_type not in ("comparison", "top_n", "aggregation")` — trend is excluded. So the structured table data sent to the frontend has no Total row, even though the model intended one.

- [ ] **Step 1: Write failing test**

```python
# In tests/unit/test_analysis_agent.py

def test_ensure_totals_row_adds_total_for_trend():
    """Trend queries should get a Total row — model output has it, pipeline must preserve it."""
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
    assert result[-1][1] == 895000  # sum of Sales column
    assert result[-1][3] == ""  # % column skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_analysis_agent.py::test_ensure_totals_row_adds_total_for_trend -v`
Expected: FAIL — returns 3 rows (trend skipped)

- [ ] **Step 3: Fix `_ensure_totals_row` to include trend**

In `backend/agents/analysis_agent.py:546`, change:
```python
# Before:
if not rows or query_type not in ("comparison", "top_n", "aggregation"):
    return rows

# After:
if not rows or query_type not in ("comparison", "top_n", "aggregation", "trend"):
    return rows
```

- [ ] **Step 4: Update existing test that validates trend is skipped**

In `tests/unit/test_analysis_agent.py`, find `test_skips_trend` (or similar) and update it to expect totals are now added for trend queries. If the test asserts trend returns unchanged rows, update it to assert a Total row is appended.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_analysis_agent.py -v -k "totals"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/analysis_agent.py tests/unit/test_analysis_agent.py
git commit -m "fix: restore trend totals in structured data — _ensure_totals_row now includes trend"
```

### Task 2: Filter Total Row from Chart Data

**Files:**
- Modify: `backend/agents/chart_agent.py:170-181` (`_format_xy_data`)
- Test: `tests/unit/test_chart_agent.py`

**Problem:** With Task 1, Total rows will be in all table data (correct for table rendering). But `_format_xy_data` sends them to the chart too, creating a misleading "Total" bar alongside individual items (visible in Turn 4 screenshot).

- [ ] **Step 1: Write failing tests**

```python
# In tests/unit/test_chart_agent.py

def test_format_xy_data_excludes_total_row():
    """Total/Grand Total rows should be excluded from chart data."""
    from backend.agents.chart_agent import _format_xy_data
    headers = ["Customer", "Sales"]
    rows = [
        ["HCODE", 1642000],
        ["SMARTBIKE", 1062000],
        ["Total", 2704000],
    ]
    data = _format_xy_data(headers, rows)
    labels = [d["label"] for d in data]
    assert "Total" not in labels
    assert len(data) == 2

def test_format_xy_data_excludes_grand_total():
    from backend.agents.chart_agent import _format_xy_data
    headers = ["Ledger", "Q2", "Q3"]
    rows = [
        ["SALES HARYANA", 895000, 975000],
        ["SALES EXPORT", 0, 182500],
        ["Grand Total", 895000, 1157500],
    ]
    data = _format_xy_data(headers, rows)
    labels = [d["label"] for d in data]
    assert "Grand Total" not in labels
    assert len(data) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::test_format_xy_data_excludes_total_row -v`
Expected: FAIL — Total is included

- [ ] **Step 3: Add Total filter to `_format_xy_data`**

In `backend/agents/chart_agent.py:170-181`:

```python
def _format_xy_data(headers: list[str], rows: list[list]) -> list[dict[str, Any]]:
    """Standard label/value format for bar and line charts."""
    data = []
    for row in rows:
        label = str(row[0]).strip() if row else ""
        # Exclude Total/Grand Total rows from chart — they belong in the table only
        if label.lower() in ("total", "grand total"):
            continue
        point: dict[str, Any] = {"label": label}
        for i, header in enumerate(headers[1:], start=1):
            if header in _EXCLUDED_CHART_COLUMNS:
                continue
            if i < len(row):
                point[header] = _to_numeric(row[i])
        data.append(point)
    return data
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: exclude Total/Grand Total rows from chart data — tables only"
```

### Task 3: Analysis Agent Prompt Fixes (Ledger Names + Chart Title + Tool-Only Computation)

**Files:**
- Modify: `backend/agents/prompts.py:206-240` (analysis agent rules)
- Test: `tests/unit/test_prompts.py`

**Problem (3 sub-issues from Turn 3 trace):**

1. **Hallucinated ledger**: AnalysisAgent received sales register vouchers where "Amit Jain (Dubai, UAE)" was the party under ledger "SALES EXPORT". Claude fabricated "SALES EXPORT (Dubai)" as a new ledger name — it doesn't exist in Tally (only SALES HARYANA, SALES EX HARYANA, SALES EXPORT).

2. **Wrong chart title**: Chart title says "Q2 vs Q3 FY25-26: Sales, Gross Profit & Net Profit Comparison" but the structured table data only has sales ledger rows — no gross profit or net profit columns.

3. **Manual computation**: Model computed per-ledger breakdowns manually (extracted SALES HARYANA = 8,95,000 by parsing individual vouchers) instead of using `compute_totals` with `group_by`. This led to the text/table mismatch: QueryAgent's `compute_totals` on all Q2 vouchers = 11,95,000, while AnalysisAgent's manual ledger extraction = 8,95,000 for SALES HARYANA alone.

- [ ] **Step 1: Write tests**

```python
# In tests/unit/test_prompts.py

def test_analysis_prompt_has_exact_ledger_names_rule():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("comparison")
    assert "exact ledger names" in prompt.lower() or "exact names from the data" in prompt.lower()

def test_analysis_prompt_has_chart_title_accuracy_rule():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("comparison")
    assert "chart title" in prompt.lower() and "match" in prompt.lower()

def test_analysis_prompt_has_tool_computation_rule():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("comparison")
    assert "never compute" in prompt.lower() or "always use tools" in prompt.lower() or "never manually" in prompt.lower()
```

- [ ] **Step 2: Add rules 10, 11, 12 to analysis agent prompt**

In `backend/agents/prompts.py`, add after rule 9 (line 239):

```python
10. **Exact ledger names**: Use ONLY the exact ledger/account names present in the Tally data. \
NEVER create, rename, or infer ledger names from voucher narrations, customer names, or \
other fields. If customer "Amit Jain (Dubai, UAE)" is booked under ledger "SALES EXPORT", \
the ledger name is "SALES EXPORT" — do NOT fabricate "SALES EXPORT (Dubai)".

11. **Chart title must match data**: The "Chart title:" line must accurately describe \
the data being charted. If the data contains only sales figures, do NOT title it \
"Gross Profit & Net Profit Comparison". Title should reflect the actual columns/metrics \
in the structured data (e.g. "Q2 vs Q3: Sales by Ledger").

12. **Never manually compute**: NEVER extract or calculate numbers by reading individual \
vouchers/records yourself. Always use compute_totals (with group_by for breakdowns), \
compute_period_comparison, or compute_trend. If you need per-ledger totals, call \
compute_totals with group_by='ledger_name'. Manual extraction leads to mismatched totals.
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_prompts.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/agents/prompts.py tests/unit/test_prompts.py
git commit -m "fix: analysis agent prompt — exact ledger names, chart title accuracy, tool-only computation"
```

### Task 4: Prompt Rule — Explain Missing Months in Trend Data

**Files:**
- Modify: `backend/agents/prompts.py` (analysis agent prompt, after rule 12)
- Test: `tests/unit/test_prompts.py`

- [ ] **Step 1: Write test**

```python
def test_analysis_prompt_has_missing_months_rule():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("trend")
    assert "no transactions" in prompt.lower() or "data gap" in prompt.lower()
```

- [ ] **Step 2: Add rule 13 to analysis agent prompt**

```python
13. **Explain data gaps**: If trend data starts mid-FY (e.g. Jul instead of Apr) or has \
months with no transactions, explicitly state this. Example: "No sales transactions were \
recorded for Apr-Jun 2025, so the trend starts from Jul 2025." Do not silently omit months.
```

- [ ] **Step 3: Run tests, commit**

```bash
git add backend/agents/prompts.py tests/unit/test_prompts.py
git commit -m "fix: analysis agent prompt — explain missing months in trend data"
```

### Task 5: Run Full Test Suite + Eval Verification

- [ ] **Step 1:** `ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest tests/unit/ tests/integration/ tests/e2e/ -v`
- [ ] **Step 2:** `cd frontend && npm test -- --run`
- [ ] **Step 3:** Rerun eval collect → judge → report
- [ ] **Step 4:** Verify acceptance criteria below

### Task 6: Strip "Chart suggestion" and "Chart title" Lines from Message Text

**Files:**
- Modify: `backend/agents/analysis_agent.py` (after extraction, before returning result)
- Test: `tests/unit/test_analysis_agent.py`

**Problem:** The analysis agent prompt instructs Claude to append "Chart suggestion: bar" and "Chart title: ..." lines to its response. `_extract_chart_suggestion()` and `_extract_chart_title()` extract these values into the result dict, but the raw lines remain in the `message` text. These internal directives are visible to the user in the chat UI.

- [ ] **Step 1: Write failing test**

```python
def test_chart_metadata_stripped_from_message():
    """Chart suggestion and Chart title lines should not appear in user-visible message."""
    # Test the stripping function directly
    from backend.agents.analysis_agent import _strip_chart_metadata
    text = """Here is the sales trend analysis.

Sales grew steadily from Jul to Dec 2025.

Chart suggestion: bar
Chart title: Monthly Sales Trend FY 2025-26"""
    result = _strip_chart_metadata(text)
    assert "Chart suggestion" not in result
    assert "Chart title" not in result
    assert "sales trend analysis" in result
```

- [ ] **Step 2: Add `_strip_chart_metadata()` function**

In `backend/agents/analysis_agent.py`, add after `_extract_chart_title()`:

```python
def _strip_chart_metadata(text: str) -> str:
    """Remove Chart suggestion/Chart title lines from message text — internal directives only."""
    text = re.sub(r'\n*\**\s*(?:chart[_\s]suggestion|suggested chart)\s*:\s*.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n*\**\s*chart[_\s]title\s*:\s*.*', '', text, flags=re.IGNORECASE)
    return text.strip()
```

- [ ] **Step 3: Call `_strip_chart_metadata` on message before returning result**

In the `_run_analysis()` method, after extracting chart_suggestion and chart_title, strip them from message:

```python
message = _strip_chart_metadata(message)
```

- [ ] **Step 4: Run tests, commit**

```bash
pytest tests/unit/test_analysis_agent.py -v -k "chart_metadata"
git add backend/agents/analysis_agent.py tests/unit/test_analysis_agent.py
git commit -m "fix: strip Chart suggestion/Chart title lines from user-visible message"
```

### Task 7: Render Tables Inline in Markdown (Like Langfuse)

**Files:**
- Modify: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/components/DataTable.tsx` (may need minor adjustments)
- Test: `frontend/src/__tests__/MessageBubble.test.tsx`

**Problem:** Currently, MessageBubble strips markdown tables from the message text (`stripMarkdownTables()` removes `|`-lines), then renders structured `data.headers`/`data.rows` via a separate `DataTable` component below the text. This:
1. Changes headers from what the model produced (e.g. "RANK, CUSTOMER, SALES AMOUNT" → "party_name, amount")
2. Separates the table from its surrounding prose context
3. Differs from Langfuse's approach where markdown tables render inline within the message flow, preserving model-authored headers and the natural reading order

**Target:** Render markdown tables inline within the message text (like Langfuse does), preserving the model's original headers and table placement. The separate DataTable component should be used as a fallback only when structured data exists but no markdown table is present in the text.

- [ ] **Step 1: Update MessageBubble to render markdown tables inline**

Instead of stripping markdown tables, render them as HTML tables via the markdown renderer (react-markdown already supports GFM tables with `remark-gfm`). Key changes:
- Remove or conditionally skip `stripMarkdownTables()` when markdown tables are present
- Add `remark-gfm` plugin to ReactMarkdown if not already present (for pipe table support)
- Style the rendered markdown tables to match DataTable's appearance (Tailwind classes)
- Keep DataTable as fallback for messages with `data.headers`/`data.rows` but no markdown table in text

- [ ] **Step 2: Style inline markdown tables**

Add CSS/Tailwind styling for markdown-rendered tables to match the existing DataTable look:
- Sortable headers (optional — can be a follow-up)
- Indian number formatting (optional — markdown tables have pre-formatted text)
- Horizontal scroll on overflow
- Consistent borders, padding, alignment

- [ ] **Step 3: Update tests**

Update MessageBubble tests to verify:
- Markdown tables render inline (not stripped)
- DataTable still renders as fallback when only structured data exists
- No duplicate tables (if both markdown and structured data exist, prefer markdown)

- [ ] **Step 4: Run tests, commit**

```bash
cd frontend && npm test -- --run
git add frontend/src/components/MessageBubble.tsx frontend/src/__tests__/MessageBubble.test.tsx
git commit -m "feat: render markdown tables inline in message — Langfuse-style"
```

### Task 8: Full Message Screenshots in Eval Collector

**Files:**
- Modify: `tests/eval/collect.py`

**Problem:** The eval collector already captures `_full.png` screenshots of the entire assistant message bubble (text + table + chart). However, the judge currently receives only chart and table screenshots for visual evaluation. The full message screenshot should be the primary screenshot sent to the judge, so it can evaluate the complete user experience (text formatting, table placement, chart context).

- [ ] **Step 1: Verify `_full.png` is captured and sent to judge**

Check that `full_screenshot` path is included in the turn result dict passed to the judge. If not, add it:

```python
turn_result["full_screenshot"] = full_screenshot
```

- [ ] **Step 2: Update judge to use full screenshot**

In `tests/eval/judge.py`, ensure the full message screenshot is included in the judge's evaluation input alongside (or instead of) individual chart/table screenshots. The full screenshot gives the judge context about how text, tables, and charts appear together.

- [ ] **Step 3: Run eval to verify**

```bash
PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173
# Verify _full.png files are in the run directory
```

- [ ] **Step 4: Commit**

```bash
git add tests/eval/collect.py tests/eval/judge.py
git commit -m "feat: full message screenshots in eval — judge sees complete user experience"
```

### Phase 8 Acceptance Criteria

1. **Turns 2/5**: Total row present in structured table data (restored from pipeline)
2. **Turn 3 chart**: No hallucinated "SALES EXPORT (Dubai)" ledger. Title matches actual data columns.
3. **Turn 3 data**: Model uses tools for all computation (no manual per-ledger extraction)
4. **Turn 4 chart**: No "Total" bar — only individual customer bars
5. **Turn 2**: Model explains why Apr-Jun has no data
6. **All tests pass**: 512+ BE, 101 FE
7. **Message text**: No "Chart suggestion:" or "Chart title:" lines visible to user
8. **Tables**: Markdown tables render inline within message (Langfuse-style), preserving model headers
9. **Eval screenshots**: Full message screenshots captured and used by judge

**Note**: Turn 3 latency (75s) and text/table total mismatch from duplicate QueryAgent/AnalysisAgent computation are **parked for Phase 4** (agent architecture redesign).

### Phase 8 Files Modified (Expected)

| # | File | Changes |
|---|------|---------|
| 1 | `backend/agents/analysis_agent.py:546` | Add `"trend"` to `_ensure_totals_row` |
| 2 | `backend/agents/chart_agent.py:170-181` | Filter Total/Grand Total from `_format_xy_data` |
| 3 | `backend/agents/prompts.py:237-260` | Add rules 10-13 to analysis agent (ledger names, chart title, tool-only computation, missing months) |
| 4 | `backend/agents/analysis_agent.py:607+` | Add `_strip_chart_metadata()`, call after extraction |
| 5 | `frontend/src/components/MessageBubble.tsx` | Render markdown tables inline, keep DataTable as fallback |
| 6 | `tests/eval/collect.py` + `tests/eval/judge.py` | Full message screenshots sent to judge |
| 7 | `tests/unit/test_analysis_agent.py` | Trend totals + chart metadata stripping tests |
| 8 | `tests/unit/test_chart_agent.py` | Total exclusion tests |
| 9 | `tests/unit/test_prompts.py` | Prompt rule tests |
| 10 | `frontend/src/__tests__/MessageBubble.test.tsx` | Inline table rendering tests |
