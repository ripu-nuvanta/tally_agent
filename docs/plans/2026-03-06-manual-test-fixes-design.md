# Manual Test Issues — Design Doc

Date: 2026-03-06

## Issues

### Issue 1: JSON Parsing + ChatResponse 500

**Problem**: Claude wraps classification JSON in markdown fences (`` ```json...``` ``), causing `json.loads()` to fail and fall back to `simple_lookup`. Separately, `ChatResponse.data` is typed as `dict | None` but orchestrator can produce `list[dict]`, causing a Pydantic validation 500 error.

**Fix**:
1. `orchestrator.py:_classify()` — strip markdown fences before `json.loads()` using regex
2. `models.py` — widen `ChatResponse.data` to `dict | list[dict] | None`
3. `chat.py` — normalize list data: if `data` is a list, wrap as `{"datasets": [...]}`

**Tests**:
- Unit: markdown fence stripping (with/without `json` tag, nested fences)
- Unit: ChatResponse accepts dict, list[dict], and None
- E2E mock: query returning multiple tool results → 200 (not 500)

---

### Issue 2 + 5: Date Resolution (combined)

**Problem**: "This month", "current quarter", "Q2" etc. not correctly interpreted. Current date is only in orchestrator prompt, not query agent. No tool for Claude to compute date ranges — it guesses and gets quarters wrong (Q2 returned full-year data).

**Fix**:
1. New `resolve_date_range` tool in `tools.py` + logic in `date_utils.py`
   - Input: `description: str` (e.g., "Q2", "this month", "last quarter")
   - Output: `{"from_date": "DD-MM-YYYY", "to_date": "DD-MM-YYYY", "description": "human-readable label"}`
   - Handles: Q1-Q4 (Indian FY), "this month", "last month", "this quarter", "last quarter", "current FY", "last FY", "last N months", "YTD"
2. Inject current date into QueryAgent system prompt (not just orchestrator)
3. Update agent prompts to instruct Claude to call `resolve_date_range` for any relative date expression

**Tests**:
- Unit: `resolve_date_range()` for all supported expressions, edge cases (Q4 crossing year boundary, leap years)
- Integration: tool execution via `execute_tool()` returns correct dates
- E2E live: "Compare Q2 vs Q3 sales" returns correct quarter data
- Eval (Playwright + LLM judge): "Show P&L this month", "Compare Q2 vs Q3 sales"

---

### Issue 3: Multiple Tables Not Rendered

**Problem**: Orchestrator only passes last dataset (`all_data[-1]`); API contract is single dict; frontend renders one `DataTable`. Claude's text response includes markdown tables which render as raw HTML instead of styled `DataTable` components.

**Fix**:
1. Backend `orchestrator.py` — when multiple datasets exist, package as `{"datasets": [d1, d2, ...]}`
2. Backend `models.py` — `ChatResponse.data` already widened in Issue 1 fix
3. Frontend `MessageBubble.tsx` — if `data.datasets` exists, render a `DataTable` per dataset
4. Frontend `MessageBubble.tsx` — strip markdown tables from message text before ReactMarkdown rendering

**Tests**:
- Unit: orchestrator multi-dataset extraction produces correct structure
- Unit: frontend renders multiple DataTables when `data.datasets` present
- Unit: markdown table stripping regex
- E2E mock: multi-dataset response renders correctly
- Eval (Playwright + LLM judge): "Compare TB of Q1 vs Q2" — judges both tables present

---

### Issue 4: Quick Action Button Tests

**Problem**: No tests for the 6 quick action buttons in `QuickActions.tsx`.

**Fix**: New test file `frontend/src/__tests__/QuickActions.test.tsx`

**Tests**:
- Unit: all 6 buttons render
- Unit: click each button → `onSelect` called with correct query string
- Unit: buttons disabled during loading
- Eval (Playwright + LLM judge): click each quick action → judge response quality

---

### Issue 6: Simple Single-Query Eval Scenarios

**Problem**: All eval scenarios are multi-turn (6-8 turns). Need simple single-query scenarios matching e2e_live test coverage.

**Fix**: New YAML scenario file `tests/eval/scenarios/simple_queries.yaml` with ~6 single-turn entries:
- Trial balance for current FY
- Profit & Loss summary
- Balance Sheet
- Outstanding receivables
- Stock summary
- Sales register

Each turn has `expect.checks` for LLM judge validation. Runs via Playwright against real frontend, judged by Claude.

---

## Architecture Impact

- New tool: `resolve_date_range` (tool #13 in Claude's tool schema)
- `ChatResponse.data` type widened (backward compatible — single dict still works)
- Frontend `MessageBubble` gains multi-table rendering
- ~6 new eval scenarios, ~15 new unit tests, ~3 new integration tests, ~2 new e2e tests
