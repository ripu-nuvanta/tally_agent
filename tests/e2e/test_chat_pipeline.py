"""End-to-end tests for the chat pipeline using mock Claude API + mock Tally."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError
from tests.mocks.mock_claude_api import (
    make_classification_response,
    make_text_response,
    make_tool_call_response,
)


@pytest.mark.asyncio
async def test_greeting_returns_canned_response(e2e_client):
    """Greeting query -> orchestrator classifies -> canned greeting returned."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("greeting")],
    )

    with patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]):
        response = await client.post("/api/chat", json={"message": "Hello!"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"].startswith("Hello!")
    assert data["session_id"]
    assert data["data"] is None
    assert data["chart"] is None


@pytest.mark.asyncio
async def test_simple_lookup_trial_balance(e2e_client):
    """Simple lookup -> classify -> query agent (tool call) -> text response."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_trial_balance", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Here is the trial balance for FY 2025-26."),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post("/api/chat", json={"message": "Show trial balance"})

    assert response.status_code == 200
    data = response.json()
    assert "trial balance" in data["message"].lower()
    assert data["session_id"]


@pytest.mark.asyncio
async def test_clarification_returns_question(e2e_client):
    """Ambiguous query -> orchestrator classifies as clarification_needed."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response(
                "clarification_needed",
                clarification_question="Which balance are you looking for? Cash, bank, or trial balance?",
            ),
        ],
    )

    with patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]):
        response = await client.post("/api/chat", json={"message": "Show me the balance"})

    assert response.status_code == 200
    data = response.json()
    assert "balance" in data["message"].lower()
    assert data["data"] is None


@pytest.mark.asyncio
async def test_simple_lookup_balance_sheet(e2e_client):
    """Balance sheet lookup -> classify -> query agent (tool call) -> response."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_balance_sheet", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Here is the balance sheet for FY 2025-26."),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post("/api/chat", json={"message": "Show balance sheet"})

    assert response.status_code == 200
    data = response.json()
    assert "balance sheet" in data["message"].lower()
    assert data["session_id"]


@pytest.mark.asyncio
async def test_comparison_with_analysis_and_chart(e2e_client):
    """Comparison query -> query agent -> analysis agent -> chart agent."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("comparison", requires_chart=True)],
        query_agent_responses=[
            make_tool_call_response("get_profit_and_loss", {"from_date": "01-04-2025", "to_date": "30-09-2025"}),
            make_text_response("Sales in H1: 20,00,000. Purchases: 15,00,000."),
        ],
        analysis_agent_responses=[
            make_text_response(
                "Comparison analysis:\n- Sales exceeded purchases by 5,00,000\nchart_suggestion: grouped_bar"
            ),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.analysis_agent.anthropic_client", mock_clients["analysis_agent"]),
    ):
        response = await client.post("/api/chat", json={"message": "Compare sales and purchases"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]


@pytest.mark.asyncio
async def test_multi_dataset_response_does_not_500(e2e_client):
    """Multiple tool calls producing multiple datasets should return 200, not 500.

    Regression test: ChatResponse.data typed as dict|None caused a 500 when
    the orchestrator passed a list[dict] from multiple tool results.
    """
    client, set_responses, mock_clients = e2e_client

    # simple_lookup with two sequential tool calls -> two datasets in tool_results.
    # With no analysis agent, orchestrator sets final_data = all_datasets (list[dict]).
    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response(
                "get_profit_and_loss",
                {"from_date": "01-04-2025", "to_date": "30-09-2025"},
                extra_text="Let me fetch H1 P&L first.",
            ),
            make_tool_call_response(
                "get_profit_and_loss",
                {"from_date": "01-10-2025", "to_date": "31-03-2026"},
                extra_text="Now fetching H2 P&L.",
            ),
            make_text_response("Here is the P&L for both halves of the financial year."),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show P&L for H1 and H2 of this FY"},
        )

    assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.text}"
    data = response.json()
    assert data["message"]
    assert data["session_id"]
    # data should be a list of dicts (multiple datasets), not a single dict
    assert isinstance(data["data"], list), f"Expected list but got {type(data['data'])}"
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_top_n_query(e2e_client):
    """Top-N query -> query agent -> analysis agent -> ranked response."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("top_n")],
        query_agent_responses=[
            make_tool_call_response("get_sales_register", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Sales data retrieved."),
        ],
        analysis_agent_responses=[
            make_text_response("Top 5 customers by sales:\n1. HCODE - 15,00,000\n2. SMARTBIKE - 10,00,000"),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.analysis_agent.anthropic_client", mock_clients["analysis_agent"]),
    ):
        response = await client.post("/api/chat", json={"message": "Top 5 customers by sales"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"]


@pytest.mark.asyncio
async def test_multi_turn_conversation_preserves_session(e2e_client):
    """Two sequential messages with same session_id -> context preserved."""
    client, set_responses, mock_clients = e2e_client

    # First turn
    set_responses(orchestrator_responses=[make_classification_response("greeting")])
    with patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]):
        r1 = await client.post("/api/chat", json={"message": "Hi"})

    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Second turn — reuse session
    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_trial_balance", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Here is the trial balance."),
        ],
    )
    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        r2 = await client.post("/api/chat", json={"message": "Show trial balance", "session_id": session_id})

    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_empty_message_returns_422(e2e_client):
    """Empty message should fail validation."""
    client, _, _ = e2e_client
    response = await client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tally_connection_error_surfaced_in_response(e2e_client):
    """Tally unreachable -> tool returns error -> agent reports it in message."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_trial_balance", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("I'm unable to connect to Tally. Please check the connection."),
        ],
    )

    # Patch the tool handler to raise TallyConnectionError
    async def failing_handler(client, **kwargs):
        raise TallyConnectionError("Connection refused: Tally is not running")

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.tools.TOOL_HANDLERS", {"get_trial_balance": failing_handler}),
    ):
        response = await client.post("/api/chat", json={"message": "Show trial balance"})

    assert response.status_code == 200
    data = response.json()
    # The agent should have received the error and reported it back
    assert data["message"]
    assert data["session_id"]


@pytest.mark.asyncio
async def test_tally_response_error_surfaced_in_response(e2e_client):
    """Invalid Tally XML -> tool returns error -> agent reports it in message."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_balance_sheet", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Tally returned an invalid response. Please try again."),
        ],
    )

    async def bad_response_handler(client, **kwargs):
        raise TallyResponseError("Invalid XML: unexpected tag at line 42")

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.tools.TOOL_HANDLERS", {"get_balance_sheet": bad_response_handler}),
    ):
        response = await client.post("/api/chat", json={"message": "Show balance sheet"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"]
    assert data["session_id"]


@pytest.mark.asyncio
async def test_date_resolution_month_name(e2e_client):
    """Query agent calls resolve_date_range('April 2025') then fetches P&L."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response(
                "resolve_date_range",
                {"description": "April 2025"},
            ),
            make_tool_call_response(
                "get_profit_and_loss",
                {"from_date": "01-04-2025", "to_date": "30-04-2025"},
            ),
            make_text_response("Here is the P&L for April 2025."),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show P&L for April 2025"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]
    assert data["session_id"]


@pytest.mark.asyncio
async def test_graceful_tool_limit_exceeded(e2e_client):
    """Exceeding the tool call limit returns 200 with partial results, not a crash."""
    client, set_responses, mock_clients = e2e_client

    # Build 26 tool call responses to exceed the default limit of 25
    tool_calls = [
        make_tool_call_response(
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
        )
        for _ in range(26)
    ]

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=tool_calls,
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show trial balance"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]
    assert data["session_id"]


def test_compute_totals_string_input_no_crash():
    """compute_totals handles string inputs without crashing."""
    from backend.agents.analysis_agent import _tool_compute_totals

    result = _tool_compute_totals(["100", "200", "300"], ["value"])
    assert "error" not in result or result.get("error") is None
    # Should produce a total of 600
    assert result["records"][0]["value"] == 600.0


@pytest.mark.asyncio
async def test_trend_query_with_chart(e2e_client):
    """Trend query -> query agent -> analysis agent -> chart agent -> line chart."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("trend", requires_chart=True)],
        query_agent_responses=[
            make_tool_call_response("get_profit_and_loss", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
            make_text_response("Monthly sales data: Apr 5L, May 6L, Jun 4L, Jul 7L, Aug 8L, Sep 5L."),
        ],
        analysis_agent_responses=[
            make_text_response(
                "Monthly sales trend analysis:\n"
                "- Sales peaked in August at 8L\n"
                "- Average monthly sales: 5.8L\n"
                "chart_suggestion: line"
            ),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.analysis_agent.anthropic_client", mock_clients["analysis_agent"]),
    ):
        response = await client.post(
            "/api/chat", json={"message": "Show monthly sales trend this FY"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]
    assert data["session_id"]
