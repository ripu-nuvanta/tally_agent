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

## Phase 2 — Chart & Data Fixes (TODO)

### Phase 2a: Critical Bug Fixes

#### Bug 4: ChartRenderer Plots All Data Keys, Ignores `y_keys` — HIGH

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

#### Bug 5: `show_legend: false` Not Respected — MEDIUM

**Fix**: `{config?.show_legend !== false && <Legend />}`

#### Bug 6: Top-N Data Table Shows Only Aggregate Total — HIGH

**Turn affected**: 4
**Fix**: Investigate `_extract_all_data` — prefer per-record results over aggregates for `top_n`.

#### Bug 7: Q3 Sales = Full-Year Total (Cumulative P&L) — MEDIUM

**Turn affected**: 3
**Fix**: Verify request_builder date bounds; may need period-only vs cumulative handling.

#### Bug 8: Chart Title Defaults to "Change % by Period" — LOW

**Fix**: Update chart agent prompt to derive title from actual y_keys.

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

#### Enhancement 12: Turn 3 Legend/Series Mismatch

**Problem**: Turn 3 comparison chart shows 4 items in legend but only 3 visible bars. The 4th (Change % = 0) renders as invisible flat bars.

**Fix**: Addressed by Enhancement 9 (ComposedChart) — Change % moves to secondary axis line, legend shows only visible series. Combined with Bug 4 fix (exclude Change from data), the grouped bar will show only Q2 and Q3.

---

## Phase 3 — Langfuse Observability (TODO)

### Completed:
- OTLP endpoint corrected to `/api/public/otel/v1/traces`
- Test script created at `scripts/test_langfuse.py`

### Remaining:
1. **Run test script** to verify traces appear in Langfuse dashboard
2. **Switch to BatchSpanProcessor** (SimpleSpanProcessor blocks event loop)
3. **Pass tracer_provider explicitly** to `AnthropicInstrumentor().instrument(tracer_provider=provider)`
4. **Install Langfuse skill** for Claude Code: `npx skills add langfuse/skills --skill "langfuse"` (blocked by disk space — retry when space available)

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

## Files to Modify (Phase 2)

| # | File | Function/Area | Items |
|---|------|---------------|-------|
| 1 | `backend/agents/chart_agent.py` | `_format_xy_data`, `_build_config` | Bug 4, Enh 9 (composed chart config, secondary_y_keys) |
| 2 | `frontend/src/components/ChartRenderer.tsx` | Full rewrite of chart rendering | Bug 4 (y_keys), Bug 5 (legend), Enh 9 (ComposedChart + dual axis), Enh 10 (colors), Enh 11 (number formatting), Enh 12 (legend fix) |
| 3 | `frontend/src/utils/format.ts` | New `formatAxisAmount` | Enh 11 (₹ K/L/Cr formatting) |
| 4 | `backend/agents/orchestrator.py` | `_extract_all_data` | Bug 6 (top-N data) |
| 5 | `backend/agents/prompts.py` | `build_chart_agent_prompt` | Bug 8 (chart title), Enh 9 (composed chart type in valid types) |
| 6 | `backend/tally_bridge/request_builder.py` | P&L date handling | Bug 7 (cumulative vs period) |

## Verification (Phase 2)

1. Run unit tests: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/`
2. Run frontend tests: `cd frontend && npm test`
3. Restart backend + frontend
4. Rerun eval: `PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173`
5. Run judge: `source .env && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY PYTHONPATH=. python tests/eval/judge.py --run-dir <run_dir>`
6. Target: All chart scores ≥ 4, factual scores ≥ 4, all turns have structured data
