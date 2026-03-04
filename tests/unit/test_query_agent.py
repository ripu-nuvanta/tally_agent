"""Unit tests for QueryAgent — Claude tool-calling loop.

Uses unittest.mock to patch the module-level anthropic_client and execute_tool
so no real API calls or Tally connections are needed.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.context import SessionContext


# ---------------------------------------------------------------------------
# Helper factories for mock Claude responses
# ---------------------------------------------------------------------------


def _make_text_response(text: str):
    """Mock Claude response with just text (end_turn)."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    return msg


def _make_tool_call_response(
    tool_name: str, tool_input: dict, tool_use_id: str = "tu_123"
):
    """Mock Claude response requesting a tool call."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_use_id
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = ""
    msg.content = [text_block, tool_block]
    return msg


# ---------------------------------------------------------------------------
# Tests: Direct text answer (no tool calls)
# ---------------------------------------------------------------------------


class TestQueryAgentDirectAnswer:
    @pytest.mark.asyncio
    async def test_direct_text_response(self):
        """Claude responds with text directly — no tool calls needed."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()  # TallyClient stub
        session = SessionContext()

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_text_response("Hello! How can I help you today?")
            )

            agent = QueryAgent()
            result = await agent.execute("Hi there", mock_client, session)

        assert result["message"] == "Hello! How can I help you today?"
        assert result["tool_results"] == []

    @pytest.mark.asyncio
    async def test_session_messages_updated(self):
        """After execution, the session should contain the user and assistant messages."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_text_response("The total sales are ₹40,34,350.")
            )

            agent = QueryAgent()
            await agent.execute("What are total sales?", mock_client, session)

        # Session should have user + assistant messages
        msgs = session.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "What are total sales?"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "The total sales are ₹40,34,350."


# ---------------------------------------------------------------------------
# Tests: Tool-calling flow
# ---------------------------------------------------------------------------


class TestQueryAgentToolCalling:
    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """Claude calls get_trial_balance once, then responds with text."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        tool_response = _make_tool_call_response(
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
            tool_use_id="tu_tb_1",
        )
        final_response = _make_text_response(
            "The trial balance shows total debits of ₹50,00,000."
        )

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
        ):
            mock_claude.messages.create = AsyncMock(
                side_effect=[tool_response, final_response]
            )
            mock_exec.return_value = {
                "success": True,
                "data": {"report_name": "Trial Balance", "entries": []},
            }

            agent = QueryAgent()
            result = await agent.execute("Show trial balance", mock_client, session)

        assert result["message"] == "The trial balance shows total debits of ₹50,00,000."
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool_name"] == "get_trial_balance"
        assert result["tool_results"][0]["tool_input"] == {
            "from_date": "01-04-2025",
            "to_date": "31-03-2026",
        }
        assert result["tool_results"][0]["result"]["success"] is True

        # execute_tool should have been called with the right args
        mock_exec.assert_awaited_once_with(
            mock_client,
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
        )

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self):
        """Claude calls search_ledger, then get_ledger_transactions, then text."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        call1 = _make_tool_call_response(
            "search_ledger",
            {"search_term": "hdfc"},
            tool_use_id="tu_search_1",
        )
        call2 = _make_tool_call_response(
            "get_ledger_transactions",
            {
                "ledger_name": "HDFC Bank",
                "from_date": "01-04-2025",
                "to_date": "31-03-2026",
            },
            tool_use_id="tu_ledger_1",
        )
        final = _make_text_response("HDFC Bank has 5 transactions totalling ₹1,50,000.")

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
        ):
            mock_claude.messages.create = AsyncMock(
                side_effect=[call1, call2, final]
            )
            mock_exec.side_effect = [
                {
                    "success": True,
                    "data": [{"name": "HDFC Bank", "group": "Bank Accounts", "closing_balance": -150000}],
                },
                {
                    "success": True,
                    "data": {"vouchers": [], "count": 5},
                },
            ]

            agent = QueryAgent()
            result = await agent.execute(
                "Show HDFC bank transactions", mock_client, session
            )

        assert len(result["tool_results"]) == 2
        assert result["tool_results"][0]["tool_name"] == "search_ledger"
        assert result["tool_results"][1]["tool_name"] == "get_ledger_transactions"
        assert result["message"] == "HDFC Bank has 5 transactions totalling ₹1,50,000."

    @pytest.mark.asyncio
    async def test_tool_error_propagated(self):
        """execute_tool returns an error — Claude receives it and responds accordingly."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        tool_call = _make_tool_call_response(
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
            tool_use_id="tu_err_1",
        )
        final = _make_text_response(
            "I couldn't fetch the trial balance because Tally is not connected."
        )

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
        ):
            mock_claude.messages.create = AsyncMock(
                side_effect=[tool_call, final]
            )
            mock_exec.return_value = {
                "error": "Connection refused: Tally is not running at localhost:9000"
            }

            agent = QueryAgent()
            result = await agent.execute("Show trial balance", mock_client, session)

        # The error result should be passed through to Claude and tracked
        assert len(result["tool_results"]) == 1
        assert "error" in result["tool_results"][0]["result"]
        assert "Connection refused" in result["tool_results"][0]["result"]["error"]
        assert "not connected" in result["message"].lower() or "couldn't" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_max_tool_calls_safety(self):
        """QueryAgent stops after max_tool_calls even if Claude keeps requesting tools."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        # Claude keeps calling the same tool forever
        infinite_tool_call = _make_tool_call_response(
            "search_ledger",
            {"search_term": "bank"},
            tool_use_id="tu_loop",
        )

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
        ):
            # Always return tool_use — never stops on its own
            mock_claude.messages.create = AsyncMock(return_value=infinite_tool_call)
            mock_exec.return_value = {
                "success": True,
                "data": [{"name": "Bank A"}],
            }

            agent = QueryAgent(max_tool_calls=2)
            result = await agent.execute("Find all banks", mock_client, session)

        assert len(result["tool_results"]) == 2
        assert "maximum" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_tool_result_passed_back_to_claude(self):
        """Verify the tool result JSON is sent back to Claude in the messages."""
        from backend.agents.query_agent import QueryAgent

        mock_client = MagicMock()
        session = SessionContext()

        tool_call = _make_tool_call_response(
            "list_companies", {}, tool_use_id="tu_co_1"
        )
        final = _make_text_response("You have 1 company: Bharat Traders.")

        tool_data = {
            "success": True,
            "data": [{"name": "Bharat Traders Pvt Ltd"}],
        }

        with (
            patch("backend.agents.query_agent.anthropic_client") as mock_claude,
            patch("backend.agents.query_agent.execute_tool", new_callable=AsyncMock) as mock_exec,
        ):
            mock_claude.messages.create = AsyncMock(
                side_effect=[tool_call, final]
            )
            mock_exec.return_value = tool_data

            agent = QueryAgent()
            await agent.execute("List companies", mock_client, session)

        # The second call to messages.create should include the tool_result message
        second_call_kwargs = mock_claude.messages.create.call_args_list[1]
        messages = second_call_kwargs.kwargs.get("messages") or second_call_kwargs[1].get("messages")
        # Find the tool_result message
        tool_result_msgs = [
            m for m in messages if m["role"] == "user"
            and isinstance(m.get("content"), list)
            and any(
                isinstance(c, dict) and c.get("type") == "tool_result"
                for c in m["content"]
            )
        ]
        assert len(tool_result_msgs) == 1
        tr_content = tool_result_msgs[0]["content"][0]
        assert tr_content["tool_use_id"] == "tu_co_1"
        assert json.loads(tr_content["content"]) == tool_data
