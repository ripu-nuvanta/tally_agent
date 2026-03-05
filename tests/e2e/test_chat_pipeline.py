"""End-to-end tests for the chat pipeline using mock Claude API + mock Tally."""

import pytest
from unittest.mock import patch

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
