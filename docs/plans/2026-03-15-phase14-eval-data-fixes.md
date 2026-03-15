# Phase 14: Eval Data Accuracy & Context Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 root-cause issues from eval runs 17-18: Turn 7 stub response (AnalysisAgent skipped), Turn 3 incorrect monthly P&L data on live Tally (cumulative passed as monthly), and judge scoring without ground truth.

**Architecture:** (A) Pass configurable session context to AnalysisAgent so it can reference prior-turn data. (B) Strengthen QueryAgent Rule 11 to be harder to ignore for monthly P&L trend queries. (C) Wire ground truth keys into eval scenarios (mock + live via generate_golden.py).

**Tech Stack:** Python, FastAPI, pytest, eval framework (collect/judge/report)

---

## Root Cause Summary

| Issue | Turn | Root Cause | Fix |
|-------|------|-----------|-----|
| Stub response, no data | T7 (live) | QueryAgent reuses prior turn data without tool calls → `raw_tally_data` empty → AnalysisAgent skipped | Task 1: Pass session context to AnalysisAgent |
| ₹49L cumulative as monthly | T3 (live) | QueryAgent ignored Rule 11, called `get_profit_and_loss` 12× instead of `get_sales_register`. Raw cumulative P&L data passed to AnalysisAgent which treated it as monthly values. QueryAgent's own text may have been correct, but AnalysisAgent re-interpreted the raw data. | Task 2: Strengthen Rule 11 + defense in depth |
| Judge can't verify factual accuracy | All turns | Scenario YAMLs have no `ground_truth_key` → judge scores on internal consistency only | Task 3: Wire ground truth keys (mock + live) |

## Key Discoveries

1. **`_handle_profit_and_loss` already calls `profit_and_loss_period()`** (subtraction is wired up in `tools.py:402-406`). The issue is NOT missing subtraction — it's that 12 raw P&L tool results get passed to AnalysisAgent which misinterprets them.

2. **Rule 11 already exists** in `prompts.py:126-135` — it tells QueryAgent to prefer voucher registers for monthly trends. The model didn't follow it in Turn 3. Need to make it harder to ignore.

3. **`tests/eval/generate_golden.py` exists** — can query live Tally to generate ground truth fixtures. Ground truth works for both mock and live scenarios.

---

### Task 1: Pass Session Context to AnalysisAgent (T7 Fix)

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/agents/analysis_agent.py:407-455`
- Modify: `backend/agents/orchestrator.py:156-160`
- Test: `tests/unit/test_analysis_agent.py`
- Test: `tests/unit/test_orchestrator.py`

#### Step 1.1: Add config setting

- [ ] **Add `ANALYSIS_CONTEXT_MESSAGES` to Settings**

```python
# In backend/config.py, add to Settings class:
ANALYSIS_CONTEXT_MESSAGES: int = 4  # Number of prior session messages passed to AnalysisAgent
```

- [ ] **Verify**: `python -c "from backend.config import settings; print(settings.ANALYSIS_CONTEXT_MESSAGES)"`
  Expected: `4`

- [ ] **Commit**: `git commit -m "feat: add ANALYSIS_CONTEXT_MESSAGES config setting"`

#### Step 1.2: Write failing test — AnalysisAgent receives session context

- [ ] **Write test in `tests/unit/test_analysis_agent.py`**

```python
@pytest.mark.asyncio
async def test_execute_receives_session_context(monkeypatch, mock_anthropic_response):
    """AnalysisAgent.execute() includes prior session messages when session is provided."""
    from backend.agents.context import SessionContext

    captured_messages = []
    original_create = analysis_agent.anthropic_client.messages.create

    async def capture_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return await original_create(**kwargs)

    # Build a session with prior turns
    session = SessionContext()
    session.add_message("user", "Show monthly sales for this FY")
    session.add_message("assistant", "Here is the monthly sales data:\nMonth | Sales\nMay 2025 | ₹49,97,900\nJun 2025 | ₹49,97,900")

    agent = AnalysisAgent()
    monkeypatch.setattr(analysis_agent.anthropic_client.messages, "create", capture_create)

    result = await agent.execute(
        raw_data=[{"account_name": "Sales", "closing_balance": 100000}],
        computed_data=None,
        user_query="What is the average monthly sales?",
        query_type="aggregation",
        session=session,
    )

    # Verify session context was included in the user message
    assert len(captured_messages) > 0
    user_content = captured_messages[0][0]["content"]
    assert "Prior Conversation Context" in user_content
    assert "monthly sales" in user_content.lower()
```

- [ ] **Run test to verify it fails**

Run: `pytest tests/unit/test_analysis_agent.py::test_execute_receives_session_context -v`
Expected: FAIL — `execute()` doesn't accept `session` parameter yet

#### Step 1.3: Implement — Add session parameter to AnalysisAgent.execute()

- [ ] **Modify `backend/agents/analysis_agent.py`**

In the `execute()` method signature (line 407), add optional `session` parameter:

```python
async def execute(
    self,
    raw_data: list | dict,
    computed_data: list | None,
    user_query: str,
    query_type: str,
    session: Any | None = None,  # SessionContext, optional
) -> dict[str, Any]:
```

After building the `parts` list (around line 454), inject session context:

```python
# Inject prior conversation context if session provided
if session and session.messages:
    from backend.config import settings as _settings
    n = _settings.ANALYSIS_CONTEXT_MESSAGES
    recent = session.messages[-n:]
    ctx_lines = []
    for msg in recent:
        role = msg["role"].capitalize()
        # Truncate each message to 500 chars to control token usage
        content = msg["content"][:500]
        ctx_lines.append(f"{role}: {content}")
    context_str = "\n\n".join(ctx_lines)
    parts.insert(0,
        "## Prior Conversation Context\n"
        "These are recent messages from the conversation. If the user's current query "
        "can be answered using data from a prior turn, reference that data.\n\n"
        f"{context_str}\n\n"
    )
```

- [ ] **Run test to verify it passes**

Run: `pytest tests/unit/test_analysis_agent.py::test_execute_receives_session_context -v`
Expected: PASS

#### Step 1.4: Write failing test — Orchestrator passes session to AnalysisAgent

- [ ] **Write test in `tests/unit/test_orchestrator.py`**

Adapt to existing test patterns in the file. Core assertion: when orchestrator calls `self.analysis_agent.execute(...)`, the `session` kwarg is passed.

- [ ] **Run test to verify it fails**, then implement.

#### Step 1.5: Implement — Pass session in Orchestrator

- [ ] **Modify `backend/agents/orchestrator.py` line 158-160**

Change:
```python
analysis_result = await self.analysis_agent.execute(
    raw_tally_data, computed_data, user_message, query_type,
)
```

To:
```python
analysis_result = await self.analysis_agent.execute(
    raw_tally_data, computed_data, user_message, query_type,
    session=session,
)
```

- [ ] **Run full unit test suite**

Run: `pytest tests/unit/ -v --tb=short -q`
Expected: All existing tests pass (session=None is the default, so no breakage)

- [ ] **Commit**: `git commit -m "feat: pass configurable session context to AnalysisAgent for prior-turn data reuse"`

---

### Task 2: Strengthen Rule 11 for Monthly P&L Trends (T3 Fix)

**Files:**
- Modify: `backend/agents/prompts.py` (Rule 11)
- Modify: `backend/agents/analysis_agent.py` (add cumulative data warning)
- Test: Existing unit tests should still pass

The existing Rule 11 (`prompts.py:126-135`) already tells QueryAgent to prefer voucher registers for monthly trends. But the model ignored it in Turn 3 and made 12 P&L calls. Two reinforcements:

#### Step 2.1: Strengthen Rule 11 wording

- [ ] **Modify Rule 11 in `backend/agents/prompts.py`**

Make the rule more emphatic and add a NEVER directive:

```
Rule 11 — One-call trend queries (CRITICAL)
For monthly/quarterly sales or purchase TRENDS:
- ALWAYS use get_sales_register or get_purchase_register (1 call, full date range).
  Voucher data includes transaction dates — group by month in the analysis phase.
- NEVER call get_profit_and_loss multiple times (once per month) for trend queries.
  P&L returns cumulative YTD figures, NOT monthly breakdowns. Calling it 12 times
  wastes 24 HTTP requests and the raw cumulative data confuses downstream analysis.
- get_profit_and_loss is ONLY for single-period aggregate P&L summaries.
- For expense trends, use get_day_book(voucher_type="Payment") or get_day_book(voucher_type="Journal").
```

- [ ] **Run unit tests**: `pytest tests/unit/ -v --tb=short -q`
Expected: All pass (prompt text change only)

#### Step 2.2: Defense in depth — AnalysisAgent cumulative data detection

- [ ] **Add warning in AnalysisAgent prompt (`build_analysis_agent_prompt()` in `prompts.py`)**

Add a rule to the AnalysisAgent prompt:

```
Rule N — Cumulative P&L data detection
If the raw data contains multiple P&L snapshots (one per month), the closing_balance
values are likely CUMULATIVE from FY start, not monthly actuals. To get monthly values:
  monthly_value = cumulative[month] - cumulative[month-1]
Watch for: identical or monotonically increasing closing_balance across months (sign of
cumulative data). If you see "Sales Accounts" with the same large value for consecutive
months, it's cumulative — subtract to isolate each month.
```

- [ ] **Run unit tests**: `pytest tests/unit/ -v --tb=short -q`
Expected: All pass

- [ ] **Commit**: `git commit -m "fix: strengthen Rule 11 for monthly trends, add cumulative P&L detection to AnalysisAgent"`

---

### Task 3: Wire Ground Truth into Eval Judge (Mock + Live)

**Files:**
- Modify: `tests/eval/scenarios/stock_reorder_mock.yaml`
- Verify: `tests/eval/generate_golden.py` (for live golden generation)
- Test: YAML validation

Ground truth works for both mock and live:
- **Mock**: `mock_golden.json` already has data. Add `ground_truth_key` to scenario YAML.
- **Live**: Run `generate_golden.py --host <IP> --port 9000` to generate live golden fixture.
  Judge naturally skips ground truth when key is missing (no changes needed for live-only scenarios).

#### Step 3.1: Add ground_truth_key to stock_reorder_mock.yaml

- [ ] **Modify `tests/eval/scenarios/stock_reorder_mock.yaml`**

Add `ground_truth_key` to each turn's `expect` block:

```yaml
turns:
  # Turn 1: stock reorder
  - query: "Which items are running low on stock..."
    expect:
      ground_truth_key: stock_summary
      # ... existing fields unchanged ...

  # Turn 2: top customers (no ground truth — sales register not in golden)
  - query: "Top 10 customers by sales amount"
    expect:
      # ... existing fields unchanged, no ground_truth_key ...

  # Turn 3: MoM growth
  - query: "What's the month-over-month growth..."
    expect:
      ground_truth_key: profit_and_loss
      # ... existing fields unchanged ...

  # Turn 4: Q3 vs Q4
  - query: "Compare Q3 and Q4 revenue and expenses"
    expect:
      ground_truth_key: profit_and_loss
      # ... existing fields unchanged ...

  # Turn 5: expense %
  - query: "What percentage of total expenses..."
    expect:
      ground_truth_key: profit_and_loss
      # ... existing fields unchanged ...

  # Turn 6: top 5 ledger change
  - query: "Show top 5 ledgers by absolute change..."
    expect:
      ground_truth_key: trial_balance
      # ... existing fields unchanged ...

  # Turn 7: avg monthly sales
  - query: "What is the average monthly sales..."
    expect:
      ground_truth_key: profit_and_loss
      # ... existing fields unchanged ...
```

- [ ] **Verify YAML is valid**: `python -c "import yaml; yaml.safe_load(open('tests/eval/scenarios/stock_reorder_mock.yaml'))"`
Expected: No errors

#### Step 3.2: Verify generate_golden.py works for live scenarios

- [ ] **Check generate_golden.py accepts --host/--port args and generates per-scenario fixtures**

Run: `PYTHONPATH=. python tests/eval/generate_golden.py --help` (or read the argparse section)

If the script generates a `{scenario_name}_golden.json` file, the same `ground_truth_key` mappings
in the YAML will work for live runs too — `collect.py` loads golden data by scenario name.

- [ ] **Commit**: `git commit -m "feat: add ground_truth_key to stock_reorder_mock eval scenario for factual verification"`

---

### Task 4: Diagnostic Logging for P&L Subtraction (T3 Investigation)

**Files:**
- Modify: `backend/tally_bridge/queries/reports.py:113-155`
- Test: Existing tests should still pass

Add logging to `profit_and_loss_period()` to capture cumulative and prior values on next live run.

#### Step 4.1: Add logging

- [ ] **Modify `profit_and_loss_period()` in `backend/tally_bridge/queries/reports.py`**

After fetching cumulative and prior P&L (lines 139-144), add:

```python
# Diagnostic: log subtraction inputs for top accounts
for row in cumulative.rows[:3]:
    name = row.get("account_name", "?")
    cum_bal = row.get("closing_balance", 0)
    prior_row = next((r for r in prior.rows if r.get("account_name") == name), {})
    prior_bal = prior_row.get("closing_balance", 0)
    logger.debug(
        "P&L period subtraction: %s — cumulative=%.2f, prior=%.2f, period=%.2f",
        name, cum_bal, prior_bal, cum_bal - prior_bal,
    )
```

- [ ] **Run unit tests**: `pytest tests/unit/test_reports.py -v --tb=short -q`
Expected: All pass

- [ ] **Commit**: `git commit -m "fix: add diagnostic logging to P&L period subtraction"`

---

### Task 5: Verify — Run Eval

Not a code task — verification after all fixes are deployed.

- [ ] **Restart backend** to pick up config/prompt changes

- [ ] **Run mock eval**:
```bash
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) \
PYTHONPATH=. python tests/eval/collect.py \
  --scenario stock_reorder_mock --tally-mode mock \
  --frontend-url http://localhost:5173 2>&1 | tee docs/eval-collect-stock-reorder-run19.log
```

- [ ] **Run judge + report**

**Expected improvements:**
- Turn 7: Should have data/table (AnalysisAgent receives session context)
- All mock turns: Judge reasoning references ground truth where `ground_truth_key` is set
- Turn 3 mock: Already works (mock uses voucher data). Live T3 should improve with stronger Rule 11.

---

## Scope Notes

**Out of scope for Phase 14:**
- Merging QueryAgent into AnalysisAgent (architecture F1) — too large
- Turn 4 live identical Q3/Q4 — will re-evaluate after Rule 11 fix steers model toward registers
- Adding sales register data to `mock_golden.json` — defer to when Turn 2 ground truth is needed
- Generating live golden fixture — requires live Tally access; user can run `generate_golden.py` when connected
