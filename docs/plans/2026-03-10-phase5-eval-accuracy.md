# Phase 5: Eval Accuracy Fixes — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix chart Change % rendering, GST consistency, and minor table/chart issues identified in eval run_20260310_154920 judge feedback.

**Architecture:** Backend-only fixes in chart_agent.py (data parsing), analysis_agent.py (prompt + trend trimming), and prompts.py (GST instructions). No frontend changes needed.

**Tech Stack:** Python, pytest

**Eval baseline (run_20260310_154920):**

| Turn | F | Q | C | Ch | Key Issue |
|------|---|---|---|----|----|
| 1 | 3 | 4 | 5 | - | P&L empty for current month (expected) |
| 2 | 4 | 5 | 5 | 4 | Change % = 0 in chart; Feb -100% should be N/A; title says Jul-Jan but data is Apr-Mar |
| 3 | 4 | 5 | 5 | 4 | Change % = 0 in chart |
| 4 | 4 | 5 | 5 | 4 | OK — minor x-axis label truncation |
| 5 | 3 | 5 | 5 | 4 | Change % = 0 in chart; GST base vs invoice confusion; ₹16.42L vs ₹15.70L unexplained |

---

## Task 1: Fix `_to_numeric` to Parse Percentage Strings

**Problem:** `_to_numeric("+1.7%")` returns 0.0 because `%` is not stripped. All Change % chart values render as 0.

**Files:**
- Modify: `backend/agents/chart_agent.py:226-236` (`_to_numeric`)
- Test: `tests/unit/test_chart_agent.py`

- [ ] **Step 1: Write failing tests**

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

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::test_to_numeric_percentage_string -v`
Expected: FAIL — `assert 0.0 == 1.7`

- [ ] **Step 3: Fix `_to_numeric` to strip `%` before parsing**

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

The only change is adding `.replace("%", "")` to the chain. This handles:
- `"+1.7%"` → `"+1.7"` → `1.7`
- `"-13.0%"` → `"-13.0"` → `-13.0`
- `"—"` → `"—"` → ValueError → `0.0`
- `"N/A"` → `"N/A"` → ValueError → `0.0`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py -v -k "to_numeric"`
Expected: all 6 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: _to_numeric strips % so Change % renders in charts"
```

---

## Task 2: Trim Trailing Zero Months from Trend Data

**Problem:** Feb 2026 shows `-100%` change (mathematically correct but misleading — no data exists). Chart title says "Jul–Jan" but data includes all 12 months Apr–Mar, creating visual noise with empty bars.

**Files:**
- Modify: `backend/agents/chart_agent.py` (new `_trim_trailing_zeros` function)
- Modify: `backend/agents/chart_agent.py:38-75` (`execute` method — call trim before format)
- Test: `tests/unit/test_chart_agent.py`

- [ ] **Step 1: Write failing tests**

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
    """Zero months between non-zero months should be preserved."""
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Period", "Sales", "Change", "Change %"]
    rows = [
        ["Apr 2025", 0, "—", "—"],
        ["May 2025", 100, "+100.00", "N/A"],
        ["Jun 2025", 0, "-100.00", "-100.0%"],
        ["Jul 2025", 200, "+200.00", "N/A"],
    ]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 4  # all kept — Jun zero is mid-sequence

def test_trim_trailing_zeros_also_trims_leading():
    """Leading all-zero rows (before any activity) should also be trimmed."""
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

def test_trim_trailing_zeros_no_value_column():
    """Non-trend data (no numeric column) should be returned unchanged."""
    from backend.agents.chart_agent import _trim_trailing_zeros
    headers = ["Customer", "Amount"]
    rows = [["HCODE", 1570000], ["SmartBike", 900000]]
    trimmed = _trim_trailing_zeros(headers, rows)
    assert len(trimmed) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::test_trim_trailing_zeros_removes_empty_tail -v`
Expected: FAIL — `ImportError: cannot import name '_trim_trailing_zeros'`

- [ ] **Step 3: Implement `_trim_trailing_zeros`**

Add to `backend/agents/chart_agent.py` after `_to_numeric`:

```python
def _trim_trailing_zeros(headers: list[str], rows: list[list]) -> list[list]:
    """Remove leading and trailing all-zero rows from trend data.

    Only applies when there's a numeric value column (index 1) to check.
    Mid-sequence zeros are preserved (e.g. a dip month between active months).
    """
    if not rows or len(headers) < 2:
        return rows

    # Find first and last non-zero value row (column index 1 = primary value)
    first_nonzero = None
    last_nonzero = None
    for i, row in enumerate(rows):
        val = _to_numeric(row[1]) if len(row) > 1 else 0
        if val != 0:
            if first_nonzero is None:
                first_nonzero = i
            last_nonzero = i

    if first_nonzero is None:
        return rows  # all zeros — return unchanged

    return rows[first_nonzero : last_nonzero + 1]
```

- [ ] **Step 4: Wire into `execute()` for trend/comparison queries**

In `backend/agents/chart_agent.py`, inside `execute()`, after extracting `rows` and before calling `_format_xy_data`, add:

```python
# Trim leading/trailing zero-value rows for trend charts
if query_type in ("trend",) and rows:
    rows = _trim_trailing_zeros(headers, rows)
```

Only for `trend` queries — comparisons (Q2 vs Q3) have a fixed structure that shouldn't be trimmed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py -v -k "trim"`
Expected: all 4 new tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "fix: trim leading/trailing zero months from trend charts"
```

---

## Task 3: Add GST Base-vs-Invoice Clarity to Analysis Prompt

**Problem:** Turn 5 shows HCODE total as ₹16,42,000 (invoice value incl. GST for Nov/Dec) but Turn 4 showed ₹15,70,000 (base value). The analysis agent doesn't explain the discrepancy or consistently handle GST.

Judge feedback: "Inconsistent treatment of GST: Nov/Dec values noted as including GST but earlier months aren't clarified on whether they include GST or not, creating confusion about comparability."

**Files:**
- Modify: `backend/agents/prompts.py:153-225` (`build_analysis_agent_prompt`)
- Test: `tests/unit/test_prompts.py` (verify prompt text contains GST rule)

- [ ] **Step 1: Write test for GST rule in prompt**

```python
# In tests/unit/test_prompts.py

def test_analysis_prompt_contains_gst_rule():
    from backend.agents.prompts import build_analysis_agent_prompt
    prompt = build_analysis_agent_prompt("trend")
    assert "GST" in prompt
    assert "base value" in prompt.lower() or "base sales" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompts.py::test_analysis_prompt_contains_gst_rule -v`
Expected: FAIL — "GST" not in prompt

- [ ] **Step 3: Add GST rule to analysis prompt**

In `backend/agents/prompts.py`, in the `build_analysis_agent_prompt` function, add rule 8 after rule 7:

```python
8. **GST / Tax handling**: Tally vouchers may include GST components \
(CGST, SGST, IGST). When analysing sales data:
   - Clearly state whether figures are "base value (excl. GST)" or \
"invoice value (incl. GST)" — never leave this ambiguous.
   - If different periods have different GST treatment (e.g. GST billing \
started mid-year), explicitly note this and reconcile the totals.
   - When a customer total differs between analyses (e.g. base vs invoice), \
explain the difference: "₹15.70L base sales + ₹72K GST = ₹16.42L invoiced".
   - Prefer base values for like-for-like comparisons across periods.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_prompts.py::test_analysis_prompt_contains_gst_rule -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/prompts.py tests/unit/test_prompts.py
git commit -m "fix: add GST base-vs-invoice rule to analysis prompt"
```

---

## Task 4: Handle N/A for Zero-to-Zero and Post-Activity Change %

**Problem:** Feb 2026 shows `-100.0%` change in the table (last real value → 0). This is mathematically correct but misleading — Feb has no data yet, not a real decline. The narrative says "should not be interpreted as zero sales" but the table contradicts this.

**Files:**
- Modify: `backend/agents/analysis_agent.py:310-341` (`_tool_compute_trend`)
- Test: `tests/unit/test_analysis_agent.py`

- [ ] **Step 1: Write failing test**

```python
def test_compute_trend_trailing_zero_shows_na():
    """When value drops to 0 after activity, Change % should be 'N/A' not '-100%'."""
    from backend.agents.analysis_agent import _tool_compute_trend
    series = [
        {"period": "Jan 2026", "value": 611850},
        {"period": "Feb 2026", "value": 0},
        {"period": "Mar 2026", "value": 0},
    ]
    result = _tool_compute_trend(series)
    rows = result["rows"]
    # Feb: drop to 0 → show "N/A (no data)" not "-100.0%"
    assert rows[1][3] == "N/A"
    # Mar: 0 → 0 → also N/A
    assert rows[2][3] == "N/A"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/test_analysis_agent.py::test_compute_trend_trailing_zero_shows_na -v`
Expected: FAIL — `assert "-100.0%" == "N/A"`

- [ ] **Step 3: Modify `_tool_compute_trend` to show N/A for drops to zero**

In `backend/agents/analysis_agent.py`, in `_tool_compute_trend`, update the percentage calculation block:

```python
        else:
            prev = float(series[i - 1].get(value_key) or 0)
            abs_chg = value - prev
            if value == 0 and prev != 0:
                # Value dropped to zero — likely no data, not a real -100% decline
                pct_chg = None
                pct_str = "N/A"
            elif prev == 0:
                pct_chg = None
                pct_str = "N/A"
            else:
                pct_chg = ((abs_chg / abs(prev)) * 100)
                pct_str = f"{pct_chg:+.1f}%"
            abs_str = f"{abs_chg:+,.2f}"
```

This changes:
- `611850 → 0` from "-100.0%" to "N/A" (no data, not a decline)
- `0 → 0` stays "N/A" (already was, via `prev == 0`)
- Real declines like `600000 → 500000` still show "-16.7%"

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_analysis_agent.py -v -k "trend"`
Expected: PASS (new test + existing tests)

Note: verify existing trend tests still pass — the `0 → 295000` case (Jul start) was already "N/A" so no change there. Any test expecting "-100.0%" for a drop-to-zero will need updating.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/analysis_agent.py tests/unit/test_analysis_agent.py
git commit -m "fix: show N/A instead of -100% for drop-to-zero in trends"
```

---

## Task 5: Run Full Test Suite + Eval Verification

- [ ] **Step 1: Run all backend tests**

```bash
ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short
```

Expected: 448+ tests pass (6+ new tests added)

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: 101 tests pass (no frontend changes)

- [ ] **Step 3: Rerun eval**

```bash
source .env && PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173
```

- [ ] **Step 4: Run judge**

```bash
source .env && ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY PYTHONPATH=. python tests/eval/judge.py --run-dir <new_run_dir>
```

- [ ] **Step 5: Generate report**

```bash
PYTHONPATH=. python tests/eval/report.py --run-dir <new_run_dir>
```

**Target scores:**
- Chart quality: ≥ 4 on all charted turns (Change % now renders correctly)
- Factual: ≥ 4 on turns 2-5 (GST clarity, consistent totals)
- No "-100%" for future/empty months

- [ ] **Step 6: Update plan and memory**

Update `docs/plans/2026-03-09-eval-regression-fixes.md` with Phase 5 results.
Update `memory/MEMORY.md` with Phase 5 status.

- [ ] **Step 7: Final commit**

```bash
git add docs/plans/
git commit -m "docs: Phase 5 eval accuracy results"
```

---

## Task 6: Debug and Fix Langfuse Session Grouping

**Problem:** `langfuse.session.id` span attribute was added to the chat endpoint (commit 02f2f1b) but sessions are not appearing grouped in Langfuse dashboard. Need to debug why and fix.

**Files:**
- Modify: `scripts/test_langfuse.py` (add session_id test)
- Modify: `backend/api/chat.py` (fix session attribute if needed)
- Possibly modify: `backend/main.py` (may need BaggageSpanProcessor for child spans)

- [ ] **Step 1: Enhance test script to verify session grouping**

Update `scripts/test_langfuse.py` to:
1. Create a root span with `langfuse.session.id` attribute
2. Make 2 Anthropic API calls within the same session span
3. Flush and check Langfuse dashboard for grouped session

```python
# Add after existing test in main():

# Test session grouping — two API calls under one session
session_id = f"test_session_{int(time.time())}"
tracer = trace.get_tracer("langfuse-test")
with tracer.start_as_current_span("session-test") as session_span:
    session_span.set_attribute("langfuse.session.id", session_id)
    logger.info("Session ID: %s", session_id)

    # First call
    response1 = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=32,
        messages=[{"role": "user", "content": "Say 'call 1'"}],
    )
    logger.info("Call 1: %s", response1.content[0].text)

    # Second call (same session)
    response2 = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=32,
        messages=[{"role": "user", "content": "Say 'call 2'"}],
    )
    logger.info("Call 2: %s", response2.content[0].text)

logger.info("Check Langfuse for session_id=%s — should show 2 traces grouped", session_id)
```

- [ ] **Step 2: Run test and check Langfuse dashboard**

```bash
PYTHONPATH=. uv run python scripts/test_langfuse.py
```

Check Langfuse Sessions tab for the test session. If not grouped:

- [ ] **Step 3: Investigate — possible causes**

1. **Attribute on wrong span**: `langfuse.session.id` may need to be on the Anthropic child spans, not just the parent. The `AnthropicInstrumentor` creates its own spans — they may not inherit parent attributes.
2. **Need BaggageSpanProcessor**: Install `opentelemetry-processor-baggage` and add `BaggageSpanProcessor(ALLOW_ALL_BAGGAGE_KEYS)` to the TracerProvider so `langfuse.session.id` propagates from parent to all child spans.
3. **Attribute set too late**: The span may need the attribute before child spans start.

```bash
pip install opentelemetry-processor-baggage
```

If BaggageSpanProcessor is needed, add to `backend/main.py` lifespan:

```python
from opentelemetry.processor.baggage import BaggageSpanProcessor, ALLOW_ALL_BAGGAGE_KEYS

provider = TracerProvider()
provider.add_span_processor(BaggageSpanProcessor(ALLOW_ALL_BAGGAGE_KEYS))
provider.add_span_processor(BatchSpanProcessor(exporter))
```

And in `backend/api/chat.py`, use baggage instead of just span attributes:

```python
from opentelemetry.baggage import set_baggage
from opentelemetry.context import attach

ctx = set_baggage("langfuse.session.id", request.session_id or session.session_id)
attach(ctx)
```

- [ ] **Step 4: Re-test with fix and verify in dashboard**

```bash
PYTHONPATH=. uv run python scripts/test_langfuse.py
```

Verify: Langfuse Sessions tab shows the test session with 2 traces grouped under it.

- [ ] **Step 5: Update pyproject.toml if needed**

If `opentelemetry-processor-baggage` is required, add it to the langfuse extra:

```toml
langfuse = [
    "langfuse>=2.0",
    "opentelemetry-sdk>=1.20",
    "opentelemetry-exporter-otlp-proto-http>=1.20",
    "opentelemetry-instrumentation-anthropic>=0.1",
    "opentelemetry-processor-baggage>=0.1",
]
```

- [ ] **Step 6: Commit**

```bash
git add scripts/test_langfuse.py backend/main.py backend/api/chat.py pyproject.toml
git commit -m "fix: Langfuse session grouping via BaggageSpanProcessor"
```

---

## Summary of Changes

| # | File | Change |
|---|------|--------|
| 1 | `backend/agents/chart_agent.py` | `_to_numeric` strips `%`; new `_trim_trailing_zeros`; wire into `execute()` |
| 2 | `backend/agents/analysis_agent.py` | `_tool_compute_trend` returns N/A for drops-to-zero |
| 3 | `backend/agents/prompts.py` | GST base-vs-invoice rule #8 in analysis prompt |
| 4 | `tests/unit/test_chart_agent.py` | +10 tests (_to_numeric, _trim_trailing_zeros) |
| 5 | `tests/unit/test_analysis_agent.py` | +1 test (trend trailing zero) |
| 6 | `tests/unit/test_prompts.py` | +1 test (GST rule presence) |
| 7 | `scripts/test_langfuse.py` | Enhanced: session grouping test with 2 API calls |
| 8 | `backend/main.py` | Possibly add BaggageSpanProcessor for session propagation |
| 9 | `backend/api/chat.py` | Possibly switch to baggage-based session_id |
| 10 | `pyproject.toml` | Possibly add `opentelemetry-processor-baggage` dep |
