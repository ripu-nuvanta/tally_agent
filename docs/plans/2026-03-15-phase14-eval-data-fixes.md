# Phase 14: Eval Data Accuracy & Context Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 root-cause issues from eval runs 17-18: Turn 7 stub response (AnalysisAgent skipped), Turn 3 incorrect monthly P&L data on live Tally (TYPE=Data P&L returns unreliable data for partial periods), and judge scoring without ground truth.

**Architecture:** (A) Pass configurable session context to AnalysisAgent so it can reference prior-turn data. (B) Make `profit_and_loss_period()` raise an error for non-full-FY ranges, forcing QueryAgent to use voucher registers. Strengthen Rule 11 as belt-and-suspenders. (C) Wire ground truth keys into eval scenarios (mock + live via generate_golden.py).

**Tech Stack:** Python, FastAPI, pytest, eval framework (collect/judge/report)

---

## Root Cause Summary

| Issue | Turn | Root Cause | Fix |
|-------|------|-----------|-----|
| Stub response, no data | T7 (live) | QueryAgent reuses prior turn data without tool calls → `raw_tally_data` empty → AnalysisAgent skipped | Task 1: Pass session context to AnalysisAgent |
| ₹49L cumulative as monthly | T3 (live) | **Tally TYPE=Data P&L returns non-monotonic, unreliable data for partial periods.** The subtraction approach in `profit_and_loss_period()` produces garbage from garbage inputs. Even if QueryAgent followed Rule 11, the 12 P&L calls would still return wrong data. | Task 2: Error on partial-period P&L + strengthen Rule 11 |
| Judge can't verify factual accuracy | All turns | Scenario YAMLs have no `ground_truth_key` → judge scores on internal consistency only | Task 3: Wire ground truth keys (mock + live) |

## Key Discoveries (Updated after live Tally diagnostic — 2026-03-15)

1. **TYPE=Data P&L returns unreliable data for partial periods.** Tested cumulative P&L for each month-end (Apr→Mar) against live Tally. Values are non-monotonic and jump between ₹49,97,900 → 0 → ₹49,97,900 → ₹2,95,000 — impossible for genuine cumulative data. The subtraction approach was doomed from the start.

2. **TYPE=Collection returns 0 for P&L ledgers.** Revenue/expense ledgers are nominal accounts that get auto-closed to "Profit & Loss A/c" at period end. ClosingBalance via Collection is always 0 by design. This is a dead end.

3. **Full-FY P&L is reliable.** Cumulative P&L to Mar 31 returns ₹49,97,900 for Sales — matches voucher-based total exactly. Only partial-period ranges are broken.

4. **Voucher-based approach is the source of truth.** `get_sales_register` returns transaction-level data that sums correctly by month: Jul ₹2,95,000 / Aug ₹3,00,000 / Sep ₹6,00,000 / ... / Feb ₹12,33,550 / Total ₹49,97,900.

5. **Rule 11 already exists** in `prompts.py:126-135` but model ignored it. Strengthening wording is belt-and-suspenders; the real fix is making the tool itself reject bad requests.

6. **`tests/eval/generate_golden.py` exists** — can query live Tally to generate ground truth fixtures.

7. **Diagnostic test script**: `test_scripts/test_pnl_period.py` (15 tests) with logs in `test_scripts/logs/` documents all findings.

---

### Task 1: Pass Session Context to AnalysisAgent (T7 Fix) — ✅ DONE (commit 651f705)

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/agents/analysis_agent.py:407-455`
- Modify: `backend/agents/orchestrator.py:156-160`
- Test: `tests/unit/test_analysis_agent.py`
- Test: `tests/unit/test_orchestrator.py`

#### Step 1.1: Add config setting

- [x] **Add `ANALYSIS_CONTEXT_MESSAGES` to Settings**

```python
# In backend/config.py, add to Settings class:
ANALYSIS_CONTEXT_MESSAGES: int = 4  # Number of prior session messages passed to AnalysisAgent
```

- [x] **Verify**: `python -c "from backend.config import settings; print(settings.ANALYSIS_CONTEXT_MESSAGES)"`
  Expected: `4`

- [x] **Commit**: `git commit -m "feat: add ANALYSIS_CONTEXT_MESSAGES config setting"`

#### Step 1.2: Write failing test — AnalysisAgent receives session context

- [x] **Write test in `tests/unit/test_analysis_agent.py`**

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

- [x] **Run test to verify it fails**

Run: `pytest tests/unit/test_analysis_agent.py::test_execute_receives_session_context -v`
Expected: FAIL — `execute()` doesn't accept `session` parameter yet

#### Step 1.3: Implement — Add session parameter to AnalysisAgent.execute()

- [x] **Modify `backend/agents/analysis_agent.py`**

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

- [x] **Run test to verify it passes**

Run: `pytest tests/unit/test_analysis_agent.py::test_execute_receives_session_context -v`
Expected: PASS

#### Step 1.4: Write failing test — Orchestrator passes session to AnalysisAgent

- [x] **Write test in `tests/unit/test_orchestrator.py`**

Adapt to existing test patterns in the file. Core assertion: when orchestrator calls `self.analysis_agent.execute(...)`, the `session` kwarg is passed.

- [x] **Run test to verify it fails**, then implement.

#### Step 1.5: Implement — Pass session in Orchestrator

- [x] **Modify `backend/agents/orchestrator.py` line 158-160**

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

- [x] **Run full unit test suite**

Run: `pytest tests/unit/ -v --tb=short -q`
Expected: All existing tests pass (session=None is the default, so no breakage)

- [x] **Commit**: `git commit -m "feat: pass configurable session context to AnalysisAgent for prior-turn data reuse"`

---

### Task 2: Error on Partial-Period P&L + Strengthen Rule 11 (T3 Fix) — ✅ DONE (commits 0e94307, 5a2c5aa)

**Files:**
- Modify: `backend/tally_bridge/queries/reports.py:89-155` (profit_and_loss_period)
- Modify: `backend/agents/prompts.py` (Rule 11)
- Test: `tests/unit/test_reports.py`
- Test: Existing unit tests should still pass

**Root cause (confirmed via diagnostic):** Tally's TYPE=Data P&L API returns non-monotonic, unreliable values for partial-period date ranges. The subtraction approach in `profit_and_loss_period()` produces garbage from garbage inputs. Full-FY P&L (cumulative to Mar 31) works correctly. Voucher registers (`get_sales_register`, `get_purchase_register`) return accurate transaction-level data.

**Fix strategy:** Two layers:
1. **Hard guard**: `profit_and_loss_period()` raises `TallyResponseError` for non-full-FY ranges, with message directing agent to use voucher registers.
2. **Soft guard**: Strengthen Rule 11 wording to reinforce voucher-based approach.

#### Step 2.1: Write failing test — partial-period P&L raises error

- [x] **Write test in `tests/unit/test_reports.py`**

```python
@pytest.mark.asyncio
async def test_profit_and_loss_period_non_full_fy_raises_error():
    """profit_and_loss_period() raises TallyResponseError for non-full-FY ranges."""
    from backend.tally_bridge.exceptions import TallyResponseError
    from backend.tally_bridge.queries.reports import profit_and_loss_period

    mock_client = AsyncMock()
    with pytest.raises(TallyResponseError, match="unreliable"):
        await profit_and_loss_period(mock_client, "01-07-2025", "31-07-2025")
```

- [x] **Run test to verify it fails**

Run: `pytest tests/unit/test_reports.py::test_profit_and_loss_period_non_full_fy_raises_error -v`
Expected: FAIL — currently does subtraction instead of raising

#### Step 2.2: Implement — Make profit_and_loss_period() reject partial periods

- [x] **Modify `profit_and_loss_period()` in `backend/tally_bridge/queries/reports.py`**

Replace the subtraction branch with an error:

```python
async def profit_and_loss_period(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    from_dt = _parse_tally_date_str(from_date)
    fy_start = get_fy_start(from_dt)

    # Full FY → fetch directly (reliable — cumulative to Mar 31 matches voucher totals)
    if from_dt == fy_start:
        return await profit_and_loss(client, from_date, to_date, company)

    # Non-full-FY → Tally TYPE=Data P&L returns unreliable data for partial periods.
    # Tested against live Tally: values are non-monotonic across date ranges.
    # Direct the agent to use voucher registers instead.
    raise TallyResponseError(
        "P&L for partial periods is unreliable via Tally's XML API. "
        "Use get_sales_register or get_purchase_register for monthly/quarterly "
        "breakdowns — they return accurate transaction-level data."
    )
```

- [x] **Run test to verify it passes**

Run: `pytest tests/unit/test_reports.py::test_profit_and_loss_period_non_full_fy_raises_error -v`
Expected: PASS

- [x] **Run full unit test suite to check for breakage**

Run: `pytest tests/unit/ -v --tb=short -q`
Expected: All pass (update any tests that expected subtraction behavior)

- [x] **Commit**: `git commit -m "fix: reject partial-period P&L requests — Tally API returns unreliable data for non-full-FY ranges"`

#### Step 2.3: Strengthen Rule 11 wording (belt-and-suspenders)

- [x] **Modify Rule 11 in `backend/agents/prompts.py`**

Make the rule more emphatic and add a NEVER directive:

```
Rule 11 — One-call trend queries (CRITICAL)
For monthly/quarterly sales or purchase TRENDS:
- ALWAYS use get_sales_register or get_purchase_register (1 call, full date range).
  Voucher data includes transaction dates — group by month in the analysis phase.
- NEVER call get_profit_and_loss multiple times (once per month) for trend queries.
  get_profit_and_loss will REJECT partial-period requests with an error.
  It is ONLY for single full-FY aggregate P&L summaries.
- For expense trends, use get_day_book(voucher_type="Payment") or get_day_book(voucher_type="Journal").
```

- [x] **Run unit tests**: `pytest tests/unit/ -v --tb=short -q`
Expected: All pass (prompt text change only)

- [x] **Commit**: `git commit -m "fix: strengthen Rule 11 — document that partial-period P&L is rejected"`

---

### Task 3: Wire Ground Truth into Eval Judge (Mock + Live) — ✅ DONE (commit 6336bc8)

**Files:**
- Modify: `tests/eval/scenarios/stock_reorder_mock.yaml`
- Verify: `tests/eval/generate_golden.py` (for live golden generation)
- Test: YAML validation

Ground truth works for both mock and live:
- **Mock**: `mock_golden.json` already has data. Add `ground_truth_key` to scenario YAML.
- **Live**: Run `generate_golden.py --host <IP> --port 9000` to generate live golden fixture.
  Judge naturally skips ground truth when key is missing (no changes needed for live-only scenarios).

#### Step 3.1: Add ground_truth_key to stock_reorder_mock.yaml

- [x] **Modify `tests/eval/scenarios/stock_reorder_mock.yaml`**

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

- [x] **Verify YAML is valid**: `python -c "import yaml; yaml.safe_load(open('tests/eval/scenarios/stock_reorder_mock.yaml'))"`
Expected: No errors

#### Step 3.2: Verify generate_golden.py works for live scenarios

- [x] **Check generate_golden.py accepts --host/--port args and generates per-scenario fixtures**

Run: `PYTHONPATH=. python tests/eval/generate_golden.py --help` (or read the argparse section)

If the script generates a `{scenario_name}_golden.json` file, the same `ground_truth_key` mappings
in the YAML will work for live runs too — `collect.py` loads golden data by scenario name.

- [x] **Commit**: `git commit -m "feat: add ground_truth_key to stock_reorder_mock eval scenario for factual verification"`

---

### Task 4: ~~Diagnostic Logging~~ — DONE (via test script)

**Status:** COMPLETE — diagnostic investigation already performed in `test_scripts/test_pnl_period.py`.

The 15-test diagnostic script confirmed:
- TYPE=Data P&L returns non-monotonic values for partial periods
- TYPE=Collection returns 0 for all P&L ledgers (nominal accounts)
- Full-FY P&L is reliable (₹49,97,900 matches voucher total)
- Voucher-based monthly breakdown is accurate

Logs preserved in `test_scripts/logs/pnl_period_debug.log`.

No further diagnostic logging needed — Task 2 replaces the subtraction code path entirely.

---

### Task 5: Verify — Run Eval (PENDING — requires backend+frontend running)

- [x] **Restart backend** to pick up config/prompt changes

- [x] **Run mock eval**:
```bash
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) \
PYTHONPATH=. python tests/eval/collect.py \
  --scenario stock_reorder_mock --tally-mode mock \
  --frontend-url http://localhost:5173 2>&1 | tee docs/eval-collect-stock-reorder-run19.log
```

- [x] **Run judge + report**

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
