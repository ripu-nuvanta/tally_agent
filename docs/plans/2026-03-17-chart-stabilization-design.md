# Chart Stabilization Design Spec

**Date**: 2026-03-17
**Status**: Draft
**Phase**: 16

## Problem Statement

Charts are unstable and produce incorrect visualizations due to multiple root causes:

1. **Data divergence**: Chart data (from STRUCTURED_RESULT) can differ from the visible markdown table
2. **Change % zeroed out**: Emoji/symbol prefixes (🔴, ▲, ▼) cause `_to_numeric()` to fail → values default to 0
3. **Scale mismatch**: Count columns (Invoices: 2-3) plotted on same Y-axis as currency (Sales: ₹7L) → bars invisible
4. **Wrong x-axis column**: Rank/# used as x-axis instead of meaningful name (Customer, Ledger)
5. **Total rows in charts**: "Total Revenue", "Total OpEx" rows skew bar chart scales
6. **Multiple tables**: When response has multiple tables, chart may pick the wrong one (e.g., filtered summary instead of main table)
7. **Percentage columns misclassified**: "Operating Profit Margin" (values 21-44%) on primary axis because header lacks "%" symbol

### Evidence: Eval Run `run_20260316_160527` (stock_reorder_mock)

| Turn | Query | Chart Score | Issues |
|------|-------|-------------|--------|
| 2 | Top 10 customers | 4/5 | Invoices bars invisible (scale mismatch), Rank as x-axis |
| 3 | MoM growth | 3/5 | Change % all zeroed, Vouchers bars invisible |
| 4 | Q3 vs Q4 | 3/5 | Change % zeroed, Operating Margin invisible (scale mismatch) |
| 7 | Monthly avg sales | 4/5 | Change % only for above-avg months, missing zero-sales months |

## Design

### Section 1: Config Kill Switch

Add `CHARTS_ENABLED: bool = True` to `backend/config.py`.

**Behavior:**

| Mode | Strip chart title/suggestion from text | Parse markdown table | Run ChartAgent | Send `chart` in response |
|------|---------------------------------------|---------------------|----------------|-------------------------|
| `CHARTS_ENABLED=True` | Yes | Yes | Yes (with chart_suggestion) | Yes (if chart produced) |
| `CHARTS_ENABLED=False` | Yes | No | No | No (`chart = None`) |

- Default is `True` (charts enabled). Can be set to `False` to hide charts.
- Chart title (e.g., `"Chart title: Q3 vs Q4..."`) and chart suggestion (e.g., `"Chart suggestion: bar"`) are **always stripped** from the user-facing message text, regardless of config.
- When enabled, `chart_suggestion` is passed to ChartAgent's `_select_chart_type()` as first-priority input (existing behavior).
- Frontend already handles absent `chart` field: `{message.chart && <ChartRenderer />}` — no frontend changes needed.
- **Interaction with `requires_chart`**: `chart = None if not CHARTS_ENABLED or not requires_chart`. Both flags must be true for chart generation. `CHARTS_ENABLED` is the global kill switch; `requires_chart` is the per-query decision from classifier + user intent.

### Section 2: Markdown Table Parser

New utility function in `backend/agents/utils.py` to replace STRUCTURED_RESULT as the chart data source.

#### Function: `parse_markdown_table_for_chart(text: str) -> dict | None`

**Input**: AnalysisAgent's message text (string containing markdown).

**Output**: `{"headers": list[str], "rows": list[list[str|float]]}` or `None`.

**Algorithm:**

1. **Find all markdown tables** in text (blocks of consecutive lines starting with `|`)
2. **Select table**: If multiple tables, pick the one with **most rows** (tie-break: prefer the later table, then most columns). Skip tables with < 2 data rows.
3. **Parse header row** → `headers: list[str]` (strip leading/trailing `|` and whitespace)
4. **Skip separator row** (`|---|---|`)
5. **Parse data rows** → attempt numeric conversion per cell

#### X-Axis Column Selection

Skip leading ordinal/index columns to find the meaningful x-axis label:

**Skip if header matches** (case-insensitive): `"Rank"`, `"#"`, `"S.No"`, `"S.No."`, `"Sr"`, `"Sr."`, `"No."`, `"Sl."`, `"Sl. No."`

**Skip if all values are sequential integers** — run `_to_numeric()` on all column values; if all results are consecutive integers (1, 2, 3... or 0, 1, 2...) → ordinal column, skip it. Reuses the shared `_to_numeric()` which already strips emoji, symbols, and formatting.

**First non-ordinal column** → x-axis label. All columns before it are excluded from chart data.

#### Numeric Conversion (single shared `_to_numeric()` in `utils.py`)

A single enhanced `_to_numeric()` function in `utils.py`, used by both the markdown parser and ChartAgent (replacing ChartAgent's local `_to_numeric()`). Strip before parsing:
- Currency: `₹`
- Formatting: `,`, `*` (bold markers), spaces
- Percentage: `%`
- Emoji: 🔴🟢✅⬇️⬆️🥇🥈🥉 and all emoji codepoints
- Arrows/symbols: `▲`, `▼`, `△`, `▽`
- Sign symbols: `+`, `−` (unicode minus U+2212 → `-`)
- Prefix text: `"— "`, `"(base)"`, `"N/A"` → return 0 or None

#### Existing Utils

`extract_structured_from_code_execution()`, `extract_code_execution_results()`, and related STRUCTURED_RESULT utils remain in codebase but become unused by the chart pipeline. No deletion.

### Section 3: ChartAgent Rule Enhancements

#### Rule A: Scale Mismatch Detection

After `_identify_numeric_columns()`, compute max absolute value per column. If any two columns have a **ratio > 100x** between their max absolute values:

- **Count columns** (header contains "Invoice", "Voucher", "Count", "No. of", "Qty", "Quantity", "Number"): **exclude from chart entirely** (counts rarely add value alongside currency values)
- **Other mismatched columns**: Move to secondary axis (if only one such column) or exclude the smaller-scale column (if multiple mismatches)

#### Rule B: Percentage Value Detection (not just header)

Current: secondary axis only if `"%"` in header name.

Enhanced: Also move to secondary axis if:
- Header contains percentage-suggestive words: `"Margin"`, `"Rate"`, `"Ratio"`, `"Growth"` (case-insensitive)

The header keyword match is the primary signal — no value range constraint needed (a 300% growth rate is still a percentage). This catches `"Operating Profit Margin"` (values 21.4, 44.4) which lacks `%` in header.

#### Rule C: Total Row Exclusion (enhanced)

Current (line 231): skips `"Total"` and `"Grand Total"` in first column.

Enhanced: After x-axis column is correctly identified (not Rank), check the x-axis column value:

```python
clean_label = label.replace("**", "").strip().lower()
if clean_label in ("total", "grand total", "net total", "sub total", "overall")
   or clean_label.startswith("total "):
    continue
```

This catches "Total Revenue", "Total OpEx", "Total Expenses" etc. Works correctly now that x-axis is the name column (not Rank).

#### Rule D: Smarter Zero Trimming

Current `_trim_trailing_zeros()`: removes leading/trailing all-zero rows.

Enhanced: Only trim edge zeros when the non-zero middle has **≥ 3 data points**. This preserves contextually meaningful zero months (e.g., Apr-Sep with no sales in Turn 7).

#### Chart Suggestion Handling

- `chart_suggestion` from AnalysisAgent is still respected as first-priority in `_select_chart_type()`
- Valid values: `"bar"`, `"grouped_bar"`, `"line"`, `"pie"`, `"stacked_bar"`, `"composed"`, `"table_only"`
- `"table_only"` → return `None` (no chart)
- Invalid/missing → fall back to query_type inference (existing behavior)

### Section 4: Prompt Changes

#### AnalysisAgent Prompts (`prompts.py`)

**Archive**: Move Rules 14-15 (STRUCTURED_RESULT format rules) to a `DEPRECATED_ANALYSIS_RULES` string constant in the same file. Not included in the active prompt. Preserved for future reference.

**Add**: New guidance rule: _"Always put the comprehensive/complete table last in your response. If you produce summary or filtered sub-tables (e.g., 'Above Average', 'Below Average'), place them before the main result table."_

**Keep**: Chart suggestion and chart title rules — AnalysisAgent continues outputting these in text (orchestrator parses and strips them).

### Section 5: Pipeline Flow Changes

#### Orchestrator (`orchestrator.py`)

**Current flow:**
```
AnalysisAgent → STRUCTURED_RESULT extraction → ChartAgent(structured_data)
```

**New flow:**
```
AnalysisAgent returns result dict:
  - result["message"] = text with markdown tables + chart metadata
  - result["data"] = {headers, rows} from STRUCTURED_RESULT (if present, for DataTable)
  - result["chart_suggestion"] = extracted chart type string

Orchestrator:
  → strip chart title/suggestion from result["message"] (always, regardless of config)
  → if CHARTS_ENABLED and requires_chart:
      parse markdown table from result["message"] → {headers, rows} for chart
      if table_only suggestion OR no table → chart = None
      else → ChartAgent.execute(table_data, query_type, chart_suggestion)
  → return response with cleaned text + data (for DataTable) + chart (or None)
```

**ChartAgent signature change:**

Current: `execute(self, data: dict, query_type: str, requires_chart: bool)`
— where `data` is the full analysis result dict, and `chart_suggestion` is extracted internally via `data.get("chart_suggestion")`

New: `execute(self, table_data: dict, query_type: str, chart_suggestion: str | None = None)`
— `table_data` is `{headers, rows}` from markdown parser
— `chart_suggestion` passed explicitly by orchestrator
— `requires_chart` check moved to orchestrator (ChartAgent always produces chart when called)

**DataTable `data` field:**

The AnalysisAgent continues to extract STRUCTURED_RESULT when present and return it as `result["data"]`. This feeds the frontend DataTable. The prompt rules for STRUCTURED_RESULT are archived (not actively enforced), but the extraction code remains — if the LLM still produces STRUCTURED_RESULT naturally, it gets captured. If not, the frontend falls back to rendering markdown tables from the message text.

The markdown table parser is used **only for chart input** — it does not replace the DataTable data source.

**Chart metadata stripping:**

Stays in `analysis_agent.py` (existing behavior). The orchestrator reads `chart_suggestion` and `chart_title` from the result dict — the analysis agent has already extracted and returned them. No location change needed.

**What changes:**
- Orchestrator calls new `parse_markdown_table_for_chart()` on message text for chart input
- ChartAgent signature updated: receives `{headers, rows}` + `chart_suggestion` directly
- `requires_chart` check moved from ChartAgent to orchestrator
- ChartAgent internals enhanced with Rules A-D

**What stays the same:**
- ChartAgent core rule-based logic (type selection, pie formatting, config building)
- Frontend `ChartRenderer` and `MessageBubble` — no changes
- AnalysisAgent's `data` field still available for DataTable rendering
- Chart suggestion obeyed when charts enabled
- Chart metadata stripping location (analysis_agent.py)

### Section 6: Testing Strategy

#### Unit Tests

**New: `test_markdown_table_parser.py`**
- Single table extraction
- Multiple tables → picks largest (most rows, tie-break: columns)
- Skip tables with < 2 data rows
- Rank/# column skipping → correct x-axis selection
- Sequential integer detection for ordinal columns
- Enhanced numeric conversion: emoji stripping (🔴, 🟢), arrow symbols (▲, ▼), unicode minus (−)
- No table in text → returns `None`
- Real-world fixture: 3-table "average monthly" case from eval transcripts (main + above-avg + below-avg → picks main)

**New: `test_chart_agent_rules.py`** (or additions to existing `test_chart_agent.py`)
- Scale mismatch detection: Invoices (2-3) vs Sales (₹7L) → Invoices excluded
- Percentage value detection: "Operating Profit Margin" (21.4, 44.4) → secondary axis
- Enhanced total row exclusion: "Total Revenue", "Total OpEx" skipped
- Smarter zero trimming: preserves zero months when middle has < 3 non-zero points
- Pie chart: expense breakdown table (Turn 5 fixture) → correct slices

**Additions to existing `test_orchestrator.py`**
- `CHARTS_ENABLED=True` → chart in response
- `CHARTS_ENABLED=False` → no chart, text still stripped of chart title/suggestion
- Chart suggestion stripped from message text in both modes

#### E2E Tests with Real Transcript Fixtures

Use actual AnalysisAgent responses from eval run `run_20260316_160527` as test fixtures:

| Fixture | Source | Validates |
|---------|--------|-----------|
| Turn 2: Top 10 customers | stock_reorder_mock | X-axis = Customer (not Rank), Invoices excluded (scale), pie/bar correct |
| Turn 3: MoM growth | stock_reorder_mock | Change % parsed correctly (emoji stripped), Vouchers excluded (scale) |
| Turn 4: Q3 vs Q4 | stock_reorder_mock | Operating Margin → secondary axis, Change % parsed, totals excluded |
| Turn 5: Expense breakdown | stock_reorder_mock | Pie chart with correct slices, text columns excluded |
| Turn 7: Monthly avg sales | stock_reorder_mock | All months' Change % parsed (including negatives), zero months preserved |

Each E2E test: feed real response text → markdown parse → ChartAgent → validate chart spec (type, y_keys, secondary_y_keys, data values, x-axis labels).

#### Playwright Visual Tests

Render chart specs from E2E tests in frontend:
- Screenshot each chart type produced (bar, grouped_bar, composed, pie)
- Compare across viewports (mobile, tablet, desktop)
- Visually verify: correct x-axis labels (names not ranks), correct data scale, no invisible bars, Change % line not flat

## Files to Modify

| File | Change |
|------|--------|
| `backend/config.py` | Add `CHARTS_ENABLED: bool = True` |
| `backend/agents/utils.py` | Add `parse_markdown_table_for_chart()` |
| `backend/agents/chart_agent.py` | Rules A-D: scale detection, % value detection, total exclusion, zero trim |
| `backend/agents/orchestrator.py` | Use markdown parser for chart input, respect `CHARTS_ENABLED`, strip title/suggestion |
| `backend/agents/prompts.py` | Archive Rules 14-15, add "comprehensive table last" guidance |
| `tests/unit/test_markdown_table_parser.py` | New: parser unit tests |
| `tests/unit/test_chart_agent.py` | Add: scale mismatch, % detection, total exclusion, zero trim tests |
| `tests/unit/test_orchestrator.py` | Add: CHARTS_ENABLED toggle tests |
| `tests/e2e/test_chart_pipeline.py` | New: E2E with real transcript fixtures (5 turns) |
| `tests/fixtures/chart_transcript_fixtures/` | New: extracted responses from eval run |

## Out of Scope

- Frontend changes (none needed)
- AnalysisAgent code_execution changes
- STRUCTURED_RESULT removal (kept but unused)
- Chart interactivity enhancements
- New chart types
