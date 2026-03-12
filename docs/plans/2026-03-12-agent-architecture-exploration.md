# Agent Architecture Exploration — Phase 4

**Date**: 2026-03-12
**Extracted from**: [`2026-03-09-eval-regression-fixes.md`](2026-03-09-eval-regression-fixes.md) (Phase 4 section)
**Status**: FUTURE — not yet started

---

## Accuracy Improvements & Agent Architecture

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

### Status after Phase 8b (run_20260311_212338)

Phase 8b implemented Option C4 (streaming handover with computed-data flag) via `_separate_tool_results()` in the orchestrator. Results:
- Turn 3 fixed: 1/1/2/1 → 4/5/5/4. No more "Reached analysis tool limit".
- **Double computation persists**: AnalysisAgent still re-computes ~5-6 redundant tool calls per session despite receiving pre-computed data in labeled prompt sections. The AnalysisAgent explicitly chooses "I'll compute using raw voucher data" — ignoring the pre-computed section.
- **However**, AnalysisAgent produces richer analysis (per-ledger breakdowns, per-vendor comparisons) beyond what QueryAgent pre-computed. So the redundancy is partial, not total.
- **Context loss**: Not observed in 5-turn eval. Session history flows well between agents. Worth revisiting with longer sessions.

### Revised Recommendation

Option C1 (remove ANALYSIS_TOOLS from QueryAgent) is now the best path forward. Since AnalysisAgent produces richer analysis anyway, letting QueryAgent focus on data-only fetching avoids the tagging complexity. Simple queries (`simple_lookup`) that don't route to AnalysisAgent would need a lightweight computation pass — either route them to AnalysisAgent too, or keep a minimal subset of tools for QueryAgent.

### Priority Assessment

**Medium**. Current eval scores are strong (avg 4.4 factual, 4.8 quality, 4.25 chart). The double computation costs ~5-6 extra tool calls (~$0.01-0.02 per query) and ~10-15s latency. Worth optimizing but not blocking.
