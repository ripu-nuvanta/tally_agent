"""Live E2E tests — real Claude API + real Tally instance.

Run with:
    RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host 192.168.18.219 --port 9000
"""

import pytest


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


async def run_until_final(orchestrator, client, session, query, max_turns=3):
    """Send query and handle follow-ups until we get a non-clarification response."""
    current_query = query
    for _turn in range(max_turns):
        result = await orchestrator.process_query(current_query, client, session)
        if result["query_type"] != "clarification_needed":
            return result
        current_query = generate_followup(result["message"], query)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_greeting(orchestrator, tally_client, session):
    result = await orchestrator.process_query("Hello!", tally_client, session)
    assert result["query_type"] == "greeting"
    assert result["message"]
    assert result["data"] is None


@pytest.mark.asyncio
async def test_live_list_companies(orchestrator, tally_client, session):
    result = await run_until_final(orchestrator, tally_client, session, "List all companies")
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_trial_balance(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show trial balance for April 2025 to March 2026",
    )
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_profit_and_loss(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "What is the profit and loss for April 2025 to March 2026?",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_balance_sheet(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show balance sheet as of March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_receivables(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show outstanding receivables",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_sales_register(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show sales register for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_top_customers(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Top 5 customers by sales for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_comparison(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Compare sales and purchases for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_clarification(orchestrator, tally_client, session):
    """Ambiguous query should get clarification or a reasonable response."""
    result = await orchestrator.process_query("Show me the balance", tally_client, session)
    assert result["message"]
    assert result["query_type"] in ("clarification_needed", "simple_lookup", "aggregation")
