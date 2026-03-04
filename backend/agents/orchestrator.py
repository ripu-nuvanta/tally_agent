"""Orchestrator — classifies user queries and routes to the appropriate agent.

The Orchestrator is the main entry point for the agent pipeline.  It uses
Claude to classify the user's natural-language query into a structured type
(e.g. simple_lookup, comparison, greeting) and then routes to the QueryAgent
for data fetching.

Exports:
    Orchestrator      — The main orchestrator class.
    anthropic_client  — Module-level AsyncAnthropic instance (patched in tests).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import anthropic

from backend.config import settings
from backend.agents.prompts import build_orchestrator_prompt
from backend.agents.query_agent import QueryAgent
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient
from backend.utils.date_utils import format_for_tally

# Module-level client — tests patch this object.
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

GREETING_RESPONSE = (
    "Hello! I'm your TallyPrime assistant. Ask me about your accounting data "
    "— balances, sales, outstanding bills, profit & loss, and more."
)


class Orchestrator:
    """Classifies user queries and routes to the appropriate agent.

    Flow:
        1. Classify the user's query via Claude.
        2. Route based on classification:
           - greeting -> canned greeting
           - clarification_needed -> return the clarification question
           - anything else -> QueryAgent
    """

    def __init__(self) -> None:
        self.query_agent = QueryAgent()

    async def process_query(
        self,
        user_message: str,
        client: TallyClient,
        session: SessionContext,
    ) -> dict[str, Any]:
        """Process a user query through classification and routing.

        Returns:
            {
                "query_type": str,
                "message": str,
                "data": dict | None,
                "chart": None,
                "session_id": str,
            }
        """
        classification = await self._classify(user_message)
        query_type = classification.get("query_type", "simple_lookup")

        # --- Greeting ---
        if query_type == "greeting":
            session.add_message("user", user_message)
            session.add_message("assistant", GREETING_RESPONSE)
            return {
                "query_type": "greeting",
                "message": GREETING_RESPONSE,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
            }

        # --- Clarification needed ---
        if query_type == "clarification_needed":
            clarification = classification.get(
                "clarification_question",
                "Could you please provide more details about what you'd like to know?",
            )
            session.add_message("user", user_message)
            session.add_message("assistant", clarification)
            return {
                "query_type": "clarification_needed",
                "message": clarification,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
            }

        # --- All other types: route to QueryAgent ---
        agent_result = await self.query_agent.execute(user_message, client, session)
        data = _extract_last_data(agent_result.get("tool_results", []))

        return {
            "query_type": query_type,
            "message": agent_result["message"],
            "data": data,
            "chart": None,
            "session_id": session.session_id,
        }

    async def _classify(self, user_message: str) -> dict:
        """Use Claude to classify the user's query into a structured type.

        Returns a dict with at least ``query_type``.  Falls back to
        ``{"query_type": "simple_lookup", "requires_chart": False}`` when
        the response cannot be parsed as JSON.
        """
        current_date = format_for_tally(date.today())
        system_prompt = build_orchestrator_prompt(current_date)

        response = await anthropic_client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"query_type": "simple_lookup", "requires_chart": False}


def _extract_last_data(tool_results: list[dict]) -> dict | None:
    """Find the last successful tool result that contains data.

    Iterates tool_results in reverse, returning the ``data`` from the first
    result where ``result.success == True`` and ``result.data`` is present.
    """
    for tr in reversed(tool_results):
        result = tr.get("result", {})
        if result.get("success") is True and result.get("data") is not None:
            return result["data"]
    return None
