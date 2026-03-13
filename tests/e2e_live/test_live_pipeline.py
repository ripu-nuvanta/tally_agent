"""Live E2E tests — real Claude API + real Tally instance.

Run with:
    RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v -s --host 192.168.18.219 --port 9000
"""

import json
import logging

import pytest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: conversation loop (handles Claude follow-ups)
# ---------------------------------------------------------------------------

FOLLOWUP_MAP = {
    "trial balance": "Show trial balance for the current financial year",
    "balance": "Show the trial balance",
    "which": "The current financial year",
    "specify": "For the current financial year April 2025 to March 2026",
    "date": "From April 2025 to March 2026",
    "period": "Current financial year",
    "company": "The currently loaded company",
}


def generate_followup(clarification_msg: str, original_query: str) -> str:
    """Generate a follow-up answer based on the clarification question."""
    lower = clarification_msg.lower()
    for keyword, response in FOLLOWUP_MAP.items():
        if keyword in lower:
            return response
    return f"{original_query} for the current financial year April 2025 to March 2026"


def log_result(test_name: str, query: str, result: dict) -> None:
    """Log the full result from the orchestrator for monitoring."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"QUERY: {query}")
    print(f"{'='*80}")
    print(f"  query_type: {result.get('query_type')}")
    print(f"  session_id: {result.get('session_id')}")

    msg = result.get("message", "")
    print(f"  message: {msg}")

    data = result.get("data")
    if data:
        if isinstance(data, dict):
            headers = data.get("headers", [])
            rows = data.get("rows", [])
            print(f"  data: {len(headers)} columns, {len(rows)} rows")
            if headers:
                print(f"    headers: {headers[:8]}{'...' if len(headers) > 8 else ''}")
            if rows:
                first = rows[0]
                preview = str(first)[:200]
                print(f"    first row: {preview}")
                if len(rows) > 1:
                    last = rows[-1]
                    print(f"    last row:  {str(last)[:200]}")
            # Show other top-level keys in data (report_name, company, etc.)
            other_keys = [k for k in data if k not in ("headers", "rows")]
            if other_keys:
                for k in other_keys[:5]:
                    v = data[k]
                    print(f"    {k}: {str(v)[:100]}")
        elif isinstance(data, list):
            print(f"  data: list with {len(data)} items")
            if data:
                print(f"    first: {str(data[0])[:200]}")
        else:
            print(f"  data: {type(data).__name__} — {str(data)[:200]}")
    else:
        print(f"  data: None")

    chart = result.get("chart")
    if chart:
        print(f"  chart: type={chart.get('type')}, title={chart.get('title')}")
        chart_data = chart.get("data", [])
        print(f"    chart data points: {len(chart_data)}")
    else:
        print(f"  chart: None")
    print(f"{'='*80}\n")


async def run_until_final(orchestrator, client, session, query, max_turns=3):
    """Send query and handle follow-ups until we get a non-clarification response."""
    current_query = query
    for turn in range(max_turns):
        result = await orchestrator.process_query(current_query, client, session)
        print(f"  [turn {turn + 1}] query_type={result['query_type']}, message={result['message'][:100]}...")
        if result["query_type"] != "clarification_needed":
            return result
        followup = generate_followup(result["message"], query)
        print(f"  [turn {turn + 1}] clarification detected, following up with: {followup}")
        current_query = followup
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_greeting(orchestrator, tally_client, session):
    query = "Hello!"
    result = await orchestrator.process_query(query, tally_client, session)
    log_result("test_live_greeting", query, result)
    assert result["query_type"] == "greeting"
    assert result["message"]
    assert result["data"] is None


@pytest.mark.asyncio
async def test_live_list_companies(orchestrator, tally_client, session):
    query = "List all companies"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_list_companies", query, result)
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_trial_balance(orchestrator, tally_client, session):
    query = "Show trial balance for April 2025 to March 2026"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_trial_balance", query, result)
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_profit_and_loss(orchestrator, tally_client, session):
    query = "What is the profit and loss for April 2025 to March 2026?"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_profit_and_loss", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_live_balance_sheet(orchestrator, tally_client, session):
    query = "Show balance sheet as of March 2026"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_balance_sheet", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_live_receivables(orchestrator, tally_client, session):
    query = "Show outstanding receivables"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_receivables", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_live_sales_register(orchestrator, tally_client, session):
    query = "Show sales register for April 2025 to March 2026"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_sales_register", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_live_top_customers(orchestrator, tally_client, session):
    query = "Top 5 customers by sales for April 2025 to March 2026"
    result = await run_until_final(orchestrator, tally_client, session, query)
    log_result("test_live_top_customers", query, result)
    assert result["message"]


# ---------------------------------------------------------------------------
# Date Validation — Phase 7: verify bad dates don't crash Tally
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_date_validation_iso_autofix(tally_client):
    """ISO dates (YYYY-MM-DD) are auto-fixed to DD-MM-YYYY before reaching Tally.

    This is the exact scenario that crashed Tally in eval run_20260311_104350.
    execute_tool must autofix the dates and Tally must respond (not crash).
    """
    from backend.agents.tools import execute_tool

    # ISO format — what Claude sometimes sends
    result = await execute_tool(tally_client, "get_trial_balance", {
        "from_date": "2025-04-01",
        "to_date": "2026-03-31",
    })
    logger.info("ISO autofix result: %s", json.dumps(result, default=str, indent=2)[:500])
    # Must succeed — dates auto-fixed to DD-MM-YYYY
    assert "error" not in result or "timed out" in result.get("error", "").lower(), (
        f"Expected success or timeout, got error: {result.get('error')}"
    )
    if result.get("success"):
        assert result["data"] is not None


@pytest.mark.asyncio
async def test_live_date_validation_garbage_rejected(tally_client):
    """Garbage dates must be rejected before reaching Tally."""
    from backend.agents.tools import execute_tool

    result = await execute_tool(tally_client, "get_sales_register", {
        "from_date": "not-a-date",
        "to_date": "31-03-2026",
    })
    logger.info("Garbage date result: %s", result)
    assert "error" in result
    assert "DD-MM-YYYY" in result["error"]


@pytest.mark.asyncio
async def test_live_date_validation_full_fy_sales_register(tally_client):
    """Full FY sales register query should work without crashing Tally."""
    from backend.agents.tools import execute_tool

    result = await execute_tool(tally_client, "get_sales_register", {
        "from_date": "01-04-2025",
        "to_date": "31-03-2026",
    })
    logger.info("Full FY sales register: %s vouchers", len(result.get("data", [])) if result.get("success") else "ERROR")
    # Must succeed or timeout (not crash)
    assert "error" not in result or "timed out" in result.get("error", "").lower(), (
        f"Expected success or timeout, got error: {result.get('error')}"
    )


@pytest.mark.asyncio
async def test_live_ledger_vouchers_date_filter(tally_client):
    """Ledger vouchers with DateRangeFilter should return filtered results."""
    from backend.agents.tools import execute_tool

    # First find a ledger that exists
    search_result = await execute_tool(tally_client, "search_ledger", {
        "search_term": "cash",
    })
    if not search_result.get("success") or not search_result["data"]:
        pytest.skip("No 'cash' ledger found in Tally")

    ledger_name = search_result["data"][0]["name"]
    logger.info("Testing ledger vouchers for: %s", ledger_name)

    result = await execute_tool(tally_client, "get_ledger_transactions", {
        "ledger_name": ledger_name,
        "from_date": "01-04-2025",
        "to_date": "31-03-2026",
    })
    logger.info("Ledger vouchers result: %s", "success" if result.get("success") else result.get("error", "unknown"))
    assert "error" not in result or "timed out" in result.get("error", "").lower()
