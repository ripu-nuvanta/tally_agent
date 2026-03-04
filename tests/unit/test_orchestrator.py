"""Unit tests for Orchestrator — query classification and routing.

Uses unittest.mock to patch the module-level anthropic_client so no real
API calls are made.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.context import SessionContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification_response(classification: dict):
    """Mock Claude response with JSON classification."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(classification)
    msg.content = [block]
    return msg


# ---------------------------------------------------------------------------
# Tests: Classification and routing
# ---------------------------------------------------------------------------


class TestOrchestratorClassification:
    @pytest.mark.asyncio
    async def test_greeting_returns_direct_response(self):
        """classification.query_type == 'greeting' -> canned response."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()  # TallyClient stub
        session = SessionContext()

        classification = {
            "query_type": "greeting",
            "requires_chart": False,
            "reasoning": "User said hello",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            result = await orch.process_query("Hello!", mock_client, session)

        assert result["query_type"] == "greeting"
        assert "TallyPrime assistant" in result["message"]
        assert result["data"] is None
        assert result["chart"] is None
        assert result["session_id"] == session.session_id

    @pytest.mark.asyncio
    async def test_clarification_needed(self):
        """classification has clarification_question -> returns the question."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "clarification_needed",
            "requires_chart": False,
            "reasoning": "User query is ambiguous",
            "clarification_question": "Which ledger are you referring to?",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            result = await orch.process_query("Show me the balance", mock_client, session)

        assert result["query_type"] == "clarification_needed"
        assert "Which ledger" in result["message"]
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_simple_lookup_routes_to_query_agent(self):
        """simple_lookup classification -> routes to query_agent.execute."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "User wants trial balance",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            # Patch the query_agent.execute method
            with patch.object(
                orch.query_agent, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "message": "The trial balance shows debits of ₹50,00,000.",
                    "tool_results": [
                        {
                            "tool_name": "get_trial_balance",
                            "tool_input": {"from_date": "01-04-2025", "to_date": "31-03-2026"},
                            "result": {
                                "success": True,
                                "data": {"report_name": "Trial Balance", "entries": []},
                            },
                        }
                    ],
                }

                result = await orch.process_query(
                    "Show trial balance", mock_client, session
                )

                mock_execute.assert_awaited_once_with(
                    "Show trial balance", mock_client, session
                )

        assert result["query_type"] == "simple_lookup"
        assert result["message"] == "The trial balance shows debits of ₹50,00,000."
        assert result["data"] == {"report_name": "Trial Balance", "entries": []}

    @pytest.mark.asyncio
    async def test_session_messages_updated(self):
        """After greeting, session has 2 messages (user + assistant)."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "greeting",
            "requires_chart": False,
            "reasoning": "User greeted",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            await orch.process_query("Hi there", mock_client, session)

        msgs = session.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hi there"
        assert msgs[1]["role"] == "assistant"
        assert "TallyPrime assistant" in msgs[1]["content"]

    @pytest.mark.asyncio
    async def test_invalid_json_classification_fallback(self):
        """Claude returns non-JSON text -> fallback to simple_lookup -> routes to query_agent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        # Return non-JSON text
        bad_response = MagicMock()
        bad_response.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "I'm not sure how to classify this query."
        bad_response.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=bad_response)

            orch = Orchestrator()

            with patch.object(
                orch.query_agent, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "message": "Here is the data you requested.",
                    "tool_results": [],
                }

                result = await orch.process_query(
                    "Something ambiguous", mock_client, session
                )

                # Should have fallen back to simple_lookup and called query_agent
                mock_execute.assert_awaited_once()

        assert result["query_type"] == "simple_lookup"
        assert result["message"] == "Here is the data you requested."
