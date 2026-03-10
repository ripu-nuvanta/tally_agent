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
3. Rerun eval: `PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173`
4. Run judge: `source .env && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY PYTHONPATH=. python tests/eval/judge.py --run-dir <run_dir>`
5. Target: All chart scores ≥ 4, factual scores ≥ 4, all turns have structured data
