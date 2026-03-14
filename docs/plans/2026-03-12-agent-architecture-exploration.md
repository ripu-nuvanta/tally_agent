# Agent Architecture Exploration — Phase 4

**Date**: 2026-03-12
**Extracted from**: [`2026-03-09-eval-regression-fixes.md`](2026-03-09-eval-regression-fixes.md) (Phase 4 section)
**Status**: PARTIALLY IMPLEMENTED — Option C1 implemented (commit 839e064)

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

**C1: Remove ANALYSIS_TOOLS from QueryAgent entirely** — IMPLEMENTED (commit 839e064)
- QueryAgent = data fetching only (TALLY_TOOLS + DATE_TOOLS)
- AnalysisAgent = sole computation authority
- Pros: Clean separation, no conflicts, ~50% fewer tool calls
- Cons: Simple queries (e.g. "what is cash balance?") that don't route to AnalysisAgent lose computation ability. Currently QueryAgent handles `simple_lookup` and `aggregation` types without AnalysisAgent.
- Risk: Breaking change — needs careful testing of all query types
- **Resolution**: Orchestrator now routes ALL queries with data to AnalysisAgent (not just _ANALYSIS_TYPES), so simple queries also get computation. Eval results confirm no regression.

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

### Implementation (2026-03-13, commit 839e064)

Option C1 was implemented as part of Phase 12 post-implementation fixes:
- QueryAgent stripped of all analysis tools and code_execution — now uses TALLY_TOOLS + DATE_TOOLS only, prompt says "DATA FETCHING agent only"
- AnalysisAgent is sole computation authority with code_execution tool (when enabled) or ANALYSIS_TOOLS (when disabled)
- Orchestrator routes ALL queries with fetched data to AnalysisAgent (not just comparison/trend/top_n types)
- Eval results (mock mode): avg factual=4.6, quality=5.0, coherence=5.0 — no regression from the architecture change

### Priority Assessment

**RESOLVED**. Option C1 implemented. Double computation eliminated.

---

## Future Architecture Explorations (from Phase 13b eval — 2026-03-14)

### F1: Merge QueryAgent into AnalysisAgent

**Problem identified in eval run 17 (Turn 7):** QueryAgent used prior conversation data (0 tool calls) to compute an answer, hitting max_tokens=1024. AnalysisAgent was skipped because `if raw_tally_data or computed_data:` was False. Result: truncated response, no chart, no structured data.

**Root question:** Do we need QueryAgent at all? If AnalysisAgent had Tally tools + code_execution, it could fetch data AND compute in one agent, eliminating:
- The handover gap (prior data not flowing to AnalysisAgent)
- The routing condition that skips AnalysisAgent
- Token waste from two-agent conversation histories

**Risks:**
- Larger tool set may confuse model (18 Tally tools + code_execution + analysis tools)
- Session context grows faster with combined history
- Need to validate with eval that single-agent doesn't regress accuracy

**Alternative (incremental):** Keep both agents but route to AnalysisAgent unconditionally for _ANALYSIS_TYPES, even when 0 tool calls. Pass QueryAgent's text response as context. Lower risk but doesn't solve the root architecture question.

### F2: Prior Conversation Data Flow

Currently AnalysisAgent receives only raw_tally_data and computed_data from tool results. It does NOT receive:
- Prior conversation context (previous turns' data)
- QueryAgent's synthesized text when it used cached/conversation data
- Session-level data cache

**Options:**
- A: Pass last N messages to AnalysisAgent (simple, but grows context)
- B: Maintain a session-level data cache that both agents read (cleaner, more work)
- C: Merge agents (F1 above) so conversation context is naturally shared

### F3: Streaming Output

Add SSE/WebSocket streaming for long-running queries (Turn 6 took 129.9s). User sees:
- "Fetching data from Tally..." → "Analyzing..." → "Generating chart..." → final response
- Requires frontend SSE handler + backend async generator

### F4: XML-Tagged Structured Output

Replace plain-text `STRUCTURED_RESULT:` prefix with XML tags for more robust parsing:
```
<Message>
User-facing narrative and analysis text here...
</Message>
<STRUCTURED_RESULT>
{"headers": [...], "rows": [...]}
</STRUCTURED_RESULT>
```

**Benefits:**
- XML tags are unambiguous (no risk of prefix appearing in normal text)
- Can add more structured sections: `<ChartSuggestion>`, `<Insights>`, etc.
- Claude models handle XML tags well in structured output
- Eliminates markdown table parsing fallback entirely

**Risks:**
- Prompt change + parser change needed
- Need to validate model compliance with XML tags via eval

---

## Company Selector — End-to-End Implementation

### Current State

The company selector exists in the UI but has no effect on query execution:

- **Frontend**: `CompanySelector` fetches companies via `GET /api/companies`, displays a dropdown, and passes the selected company in the `POST /api/chat` request body.
- **Backend chat endpoint**: Stores `company` in `SessionContext` when received from the frontend.
- **Orchestrator / QueryAgent**: Never read `session.company` — it is stored but completely unused.
- **Tally Bridge**: `request_builder.py` supports `<SVCurrentCompany>` in XML envelopes, but no tool handler ever passes it through.
- **Mock mode**: `mock_handler.py` ignores company entirely — it pattern-matches report names only.
- **Net effect**: The company dropdown is display-only. All queries execute against Tally's currently active company regardless of the user's selection.

### What Needs to Be Done

1. **Extract company in orchestrator**: Read `company = session.company` in `orchestrator.process_query()` and make it available to the agent pipeline.
2. **Include company in Claude's system prompt**: Add the selected company name to the system prompt so Claude knows which company context it is operating in (e.g., "You are querying data for company: Bharat Traders Pvt Ltd").
3. **Auto-populate company in tool inputs**: Before dispatching tool calls to Tally, inject the company parameter into tool handler kwargs — rather than relying on Claude to pass it explicitly. This avoids prompt-following failures.
4. **Ensure all `request_builder.py` calls include `<SVCurrentCompany>`**: When a company is specified, every XML request envelope must include the `<SVCurrentCompany>` element so Tally scopes the query to that company.
5. **Mock mode company filtering** (low priority): Optionally differentiate responses by company in `mock_handler.py`. For the single-company demo this is not critical, but the hook should exist for future multi-company support.

### Implementation Notes

- The `<SVCurrentCompany>` element is already templated in `request_builder.py` but never populated. The plumbing exists; it just needs to be connected.
- Tool handlers in `tools.py` receive kwargs from `execute_tool()` — adding a `company` kwarg and forwarding it to the bridge client is straightforward.
- For the system prompt, the company name should come from `SessionContext`, not from the tool result, to avoid a chicken-and-egg problem.
- Multi-company Tally setups are common in Indian businesses (e.g., separate companies for GST registrations). This feature becomes essential when targeting real deployments.

### Priority Assessment

**Medium-High**. The feature is user-visible (dropdown exists, does nothing) which creates a UX trust issue. Implementation is low-risk and moderate effort (~50-100 LOC across 4-5 files). Should be addressed before any public demo or user testing.
