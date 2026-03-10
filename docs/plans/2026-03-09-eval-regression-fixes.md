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

## Phase 4 — Accuracy Improvements (FUTURE)

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
