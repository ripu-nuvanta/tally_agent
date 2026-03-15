# Phase 15: Architecture Bug Fixes — Unconditional AnalysisAgent & Context Window

**Date**: 2026-03-15
**Status**: COMPLETE — commits d788cc5 (impl), eval verified run 22
**Depends on**: Phase 14 (session context for AnalysisAgent — commit 651f705)
**Eval Runs**: run_20260315_182422 (mock pre-fix), run_20260315_182613 (mock pre-fix run 2), run_20260315_203851 (mock post-fix), run_20260315_204641 (live post-fix)

### Post-fix Eval Results (arch_bug_regression_mock, run 22)
| Turn | Query | Mock F/Q/C/Ch | Live F/Q/C/Ch |
|------|-------|---------------|---------------|
| 1 | MoM growth | 5/5/5/4 | 5/5/4/4 |
| 2 | Avg monthly (follow-up) | 5/5/5/5 | 5/5/5/4 |

Bug 1 confirmed fixed: Turn 2 went from 1/1/3/— (run 21) to 5/5/5/5.

### Additional fix: Eval collector tally mode toggle
collect.py only toggled to mock mode but never back to live — if a prior run left backend in mock, "live" runs stayed in mock. Fixed to explicitly toggle both directions.

---

## Summary of Findings

Three architecture bugs identified in the stock_reorder_mock eval (7-turn session):

### Bug 1: Turn 7 — QueryAgent skips re-fetch, AnalysisAgent never invoked

QueryAgent sees prior conversation history containing sales register data from Turn 3. Instead of calling tools, it says "passing to computation agent" with 0 tool calls. The Orchestrator gate at line 156:

```python
if raw_tally_data or computed_data:
```

evaluates to False (both empty), so AnalysisAgent is **skipped entirely**. The user receives QueryAgent's internal status message instead of actual analysis. Latency was 7s (vs 50-125s for normal turns).

Phase 14 added session context to AnalysisAgent (commit 651f705), but this only helps when AnalysisAgent is actually invoked. The gate condition still blocks it.

### Bug 2: Turn 6 — Mock TB not date-aware + QueryAgent max_tokens truncation

**Root cause chain**:
1. Mock handler returns identical Trial Balance regardless of date range (`Trial Balance` is in `STATIC_FIXTURES`, not `DATE_AWARE_REPORTS`). Both Q3 and Q4 TB calls return full-FY data.
2. Both runs detected the problem and attempted recovery. Divergence was LLM non-determinism:
   - Run 1: Batched 3 calls (list_all_ledgers + day_book Q3 + day_book Q4) → correct Q3/Q4 split
   - Run 2: Tried individual `get_ledger_transactions` per ledger → hit **max_tokens=1024** (`stop_reason=max_tokens`) → truncated tool calls → AnalysisAgent only had `list_all_ledgers` (full-year) → fell back to opening-to-closing change
3. Q4 purchase figure inconsistency between Turn 4 and Turn 6 is a downstream consequence of this truncation

### Bug 3: Turn 6 chart data zeroed out

Chart data showed Q3=0, Q4=0 for HP India Sales and Samsung India Electronics despite correct table values. Likely a chart agent parsing bug with negative numbers or specific ledger name patterns.

### Design Decision: Unconditional AnalysisAgent

**Proposal**: AnalysisAgent should ALWAYS run for non-greeting, non-clarification queries. Rationale:
- QueryAgent response is truncated (max_tokens=1024) and not trusted for direct user display
- Even with 0 tool calls, AnalysisAgent can use session context to analyze prior-turn data
- Directly fixes Bug 1 and improves robustness for follow-up questions
- Combined with increased context window, handles the "data in prior turn" pattern

---

## Task Breakdown

### Task 1: Make AnalysisAgent invocation unconditional

**Goal**: Remove the `if raw_tally_data or computed_data:` gate so AnalysisAgent always runs.

**Files to modify**:
- `backend/agents/orchestrator.py` (lines 152-176)

**Approach**:
1. Remove the `if raw_tally_data or computed_data:` conditional at line 156
2. Always invoke `self.analysis_agent.execute()` for non-greeting/non-clarification queries
3. When `raw_tally_data` and `computed_data` are both empty, pass empty lists — AnalysisAgent already handles this via session context
4. Remove the `analysis_result = None` fallback at line 175
5. Update the `chart_input` fallback at line 180

**Acceptance criteria**:
- [ ] AnalysisAgent is invoked for every non-greeting query, regardless of tool_results count
- [ ] When QueryAgent returns 0 tool calls, AnalysisAgent receives session context and produces analysis
- [ ] Existing tests pass — no regression for queries where QueryAgent returns data
- [ ] New unit test: orchestrator invokes AnalysisAgent when QueryAgent returns empty tool_results

### Task 2: Strengthen QueryAgent re-fetch prompt rule

**Goal**: Ensure QueryAgent always calls tools, even when conversation history contains prior results.

**Files to modify**:
- `backend/agents/prompts.py` — `build_query_agent_prompt()` function

**Approach**: Add new prompt rule:
```
13. **Always fetch fresh data**: ALWAYS call Tally tools to fetch data for the current query,
even if similar data appears in the conversation history. Prior data may be for different
date ranges, ledgers, or filters. Never skip tool calls because "data was already fetched."
The analysis agent needs current tool results to produce accurate responses.
```

Defense-in-depth alongside Task 1.

Also add a rule for quarterly comparison strategy:
```
14. **Quarterly comparisons — use day book, not trial balance**: Trial Balance from Tally is NOT
date-aware — it always returns full-FY cumulative figures regardless of date parameters.
For quarterly or period-based comparisons, ALWAYS use get_day_book(from_date, to_date) for each
period to get voucher-level transactions, then let the analysis agent compute per-ledger totals.
Never call get_trial_balance with quarterly dates expecting period-specific data.
```

**Acceptance criteria**:
- [ ] New Rule 13 (re-fetch) added to QueryAgent prompt (both code_execution_enabled and disabled variants)
- [ ] New Rule 14 (day book for quarters) added to QueryAgent prompt
- [ ] Existing prompt tests updated if any assert on prompt content

### Task 3: Increase ANALYSIS_CONTEXT_MESSAGES for long conversations

**Goal**: Ensure AnalysisAgent can see data from earlier turns in long conversations.

**Files to modify**:
- `backend/config.py` — `ANALYSIS_CONTEXT_MESSAGES` default
- `backend/agents/analysis_agent.py` — context truncation logic (lines 459-473)

**Approach**:
1. **Increase default from 4 to 8**: Covers up to 4 prior turns (user+assistant pairs). For a 7-turn session, captures turns 4-7 data.
2. **Increase per-message truncation from 500 to 1500 chars**: Tool result summaries in session messages can be long. 500 chars truncates most data tables. 1500 chars captures key data while staying within reasonable token limits.

**Token budget**: 8 messages × 1500 chars ≈ 3K tokens. AnalysisAgent max_tokens=16384, so acceptable overhead.

**Acceptance criteria**:
- [ ] `ANALYSIS_CONTEXT_MESSAGES` default changed from 4 to 8
- [ ] Per-message truncation changed from 500 to 1500 chars
- [ ] Existing unit tests for AnalysisAgent session context still pass
- [ ] New unit test: verify 8 messages are passed when session has 10+ messages

### Task 4: Increase QueryAgent max_tokens to prevent truncation

**Goal**: Prevent `stop_reason=max_tokens` when QueryAgent needs multiple parallel tool calls.

**Files to modify**:
- `backend/agents/query_agent.py` — max_tokens setting

**Approach**:
- Increase QueryAgent max_tokens from 1024 to 2048
- 1024 was set in Phase 12 to keep it lean, but it's too restrictive when the LLM needs to emit many parallel tool_use blocks (e.g., Turn 6 Run 2 tried ~11 tool_use blocks)
- 2048 allows ~8-10 parallel tool calls while still preventing excessive text generation

**Acceptance criteria**:
- [ ] QueryAgent max_tokens changed from 1024 to 2048
- [ ] No regression in existing tests
- [ ] Log a warning when `stop_reason=max_tokens` is encountered (defense-in-depth)

### Task 5: Create mini eval scenario for architecture bug regression

**Goal**: Create a focused 2-turn eval scenario that reproduces Bug 1.

**Files to create**:
- `tests/eval/scenarios/arch_bug_regression_mock.yaml`

**Scenario**:
```yaml
name: "Architecture Bug Regression (Mock)"
description: "Validates that follow-up queries using prior-turn data produce full analysis. Regression test for Bug 1 (AnalysisAgent skipped when QueryAgent makes 0 tool calls)."
tags: [architecture, regression, follow_up, context, mock]

turns:
  # Turn 1: Establish data — fetch monthly sales
  - query: "What's the month-over-month growth in sales for this FY?"
    expect:
      ground_truth_key: profit_and_loss
      query_type: trend
      has_data: true
      has_chart: true
      chart_type: [line, composed, bar]
      checks:
        - "Shows monthly sales amounts with MoM growth"
        - "Data table has multiple months of data"
        - "Chart renders with sales trend"

  # Turn 2: Follow-up — tests data re-use / re-fetch
  - query: "What is the average monthly sales amount for this FY and which months were above average?"
    expect:
      ground_truth_key: profit_and_loss
      query_type: trend
      has_data: true
      has_chart: true
      chart_type: [bar, line, composed]
      checks:
        - "Response contains actual sales data — NOT an internal status message like 'passing to computation agent'"
        - "Average monthly sales is computed (not zero or blank)"
        - "Each month is identified as above or below average"
        - "At least 3 months of data are shown"
        - "Data table has numeric values (not all zeros)"
```

**Acceptance criteria**:
- [ ] Scenario file created with 2 turns
- [ ] First check in Turn 2 explicitly tests for Bug 1 symptom
- [ ] Scenario runs in mock mode

---

## Build & Test Sequence

### Phase A: Core fixes (Tasks 1 + 2 + 3 + 4) — single commit

```bash
# 1. Implement all core changes
# Edit: orchestrator.py, prompts.py, config.py, analysis_agent.py, query_agent.py

# 2. Run all backend tests
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/
```

### Phase B: Eval scenario (Task 5) — separate commit

```bash
# 1. Create scenario file
# Create: tests/eval/scenarios/arch_bug_regression_mock.yaml

# 2. Run mini eval (2 turns)
# ⚠️ EXPENSIVE: tee to log
PYTHONPATH=. python tests/eval/collect.py --scenario arch_bug_regression_mock --frontend-url http://localhost:5173 --tally-mode mock 2>&1 | tee docs/eval-collect-arch-regression.log
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) PYTHONPATH=. python tests/eval/judge.py 2>&1 | tee docs/eval-judge-arch-regression.log
```

### Phase C: Full stock_reorder_mock re-eval — verify fixes

```bash
# ⚠️ EXPENSIVE: tee to log
PYTHONPATH=. python tests/eval/collect.py --scenario stock_reorder_mock --frontend-url http://localhost:5173 --tally-mode mock 2>&1 | tee docs/eval-collect-stock-reorder-mock-phase15.log
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) PYTHONPATH=. python tests/eval/judge.py 2>&1 | tee docs/eval-judge-stock-reorder-mock-phase15.log
```

---

## Dependencies

```
Task 1 (unconditional AnalysisAgent) ← no deps, core fix
Task 2 (prompt rules: re-fetch + day book for quarters) ← no deps, defense-in-depth
Task 3 (context window) ← no deps, amplifies Task 1
Task 4 (max_tokens) ← no deps, fixes Turn 6 truncation
Task 5 (eval scenario) ← depends on Tasks 1-4 being implemented
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Unconditional AnalysisAgent adds latency for simple queries | Medium | Low | AnalysisAgent with empty data + context returns quickly (~2-3s) |
| Increased context window hits token limits | Low | Low | 8 × 1500 chars ≈ 3K tokens, well within budget |
| QueryAgent still skips re-fetch despite prompt rule | Medium | Low | Task 1 ensures AnalysisAgent runs regardless |
| Turn 6 chart zeroing is a separate bug | High | Low | Not addressed here — track as Phase 15b |

---

## Expected Test Impact

- Backend: +3-5 new unit tests (orchestrator routing, context window, max_tokens warning)
- Eval: +1 new scenario (2 turns), total scenarios 15 (87 turns)
- No test removals expected

## Not Addressed (Future Work)

- Turn 6 chart data zeroing (separate chart_agent bug)
- Q3/Q4 golden data for judge factual verification
- Turn 2 chart x-axis using ranks instead of customer names
- Turn 1 "months" vs "days" of stock remaining

## Key Learning: Trial Balance is NOT Date-Aware

Tally's Trial Balance API (both live and mock) always returns full-FY cumulative figures regardless of SVFROMDATE/SVTODATE parameters. This is a Tally API limitation, not a mock handler bug. The correct approach for quarterly comparisons is to use `get_day_book` for each period and compute per-ledger totals from voucher-level data. Task 2's Rule 14 encodes this knowledge in the QueryAgent prompt.
