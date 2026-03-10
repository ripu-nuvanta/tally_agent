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
import re
import logging
from datetime import date
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.agents.prompts import build_orchestrator_prompt
from backend.agents.query_agent import QueryAgent
from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.chart_agent import ChartAgent
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient
from backend.utils.date_utils import format_for_tally

# Query types that require analysis post-processing
_ANALYSIS_TYPES = {"comparison", "trend", "top_n", "aggregation"}

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
        self.analysis_agent = AnalysisAgent()
        self.chart_agent = ChartAgent()

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
        classification = await self._classify(user_message, session)
        query_type = classification.get("query_type", "simple_lookup")
        requires_chart = classification.get("requires_chart", False)

        # Auto-enable chart for chart-worthy query types
        if not requires_chart and query_type in ("trend", "comparison", "top_n", "aggregation"):
            requires_chart = True
            logger.info("Orchestrator — auto-enabling chart for query_type=%s", query_type)

        logger.info(
            "Orchestrator — classified %r as query_type=%s, requires_chart=%s",
            user_message[:80], query_type, requires_chart,
        )

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
        logger.info("Orchestrator — routing to QueryAgent")
        agent_result = await self.query_agent.execute(user_message, client, session)
        tool_results = agent_result.get("tool_results", [])
        all_data = _extract_all_data(tool_results)
        raw_data = all_data[-1] if all_data else None
        all_datasets = all_data if len(all_data) > 1 else None

        logger.info(
            "Orchestrator — QueryAgent returned %d tool call(s), %d data set(s)",
            len(tool_results), len(all_data),
        )

        # --- Analysis Agent (for comparison/trend/top_n/aggregation) ---
        message = agent_result["message"]
        data = raw_data

        if query_type in _ANALYSIS_TYPES and raw_data is not None:
            logger.info("Orchestrator — routing to AnalysisAgent (query_type=%s)", query_type)
            analysis_input = all_data if len(all_data) > 1 else raw_data
            analysis_result = await self.analysis_agent.execute(
                analysis_input, user_message, query_type,
            )
            message = analysis_result["message"]
            data = analysis_result.get("data", raw_data)
            logger.info(
                "Orchestrator — AnalysisAgent returned %d tool call(s), chart_suggestion=%s",
                len(analysis_result.get("tool_results", [])),
                analysis_result.get("chart_suggestion"),
            )

            # Replace the query agent's assistant message with the analysis result
            # so session history reflects what the user actually sees.
            if session.messages and session.messages[-1]["role"] == "assistant":
                session.messages[-1]["content"] = message
        else:
            analysis_result = None

        # --- Chart Agent (when chart is needed) ---
        chart = None
        if requires_chart:
            chart_input = analysis_result if analysis_result is not None else {"data": raw_data}
            chart = self.chart_agent.execute(chart_input, query_type, requires_chart)

        # For multi-dataset responses where analysis didn't merge them, pass all datasets
        final_data = data
        if all_datasets is not None and analysis_result is None:
            final_data = _flatten_datasets(all_datasets)

        return {
            "query_type": query_type,
            "message": message,
            "data": final_data,
            "chart": chart,
            "session_id": session.session_id,
        }

    async def _classify(self, user_message: str, session: SessionContext | None = None) -> dict:
        """Use Claude to classify the user's query into a structured type.

        Returns a dict with at least ``query_type``.  Falls back to
        ``{"query_type": "simple_lookup", "requires_chart": False}`` when
        the response cannot be parsed as JSON.
        """
        current_date = format_for_tally(date.today())
        system_prompt = build_orchestrator_prompt(current_date)

        # Build messages with conversation context for better classification
        messages: list[dict[str, Any]] = []
        if session and session.messages:
            # Last 4 messages for context
            recent = session.messages[-4:]
            for msg in recent:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await anthropic_client.messages.create(
                model=settings.CLAUDE_CLASSIFIER_MODEL,
                max_tokens=512,
                system=system_prompt,
                messages=messages,
            )
        except anthropic.APIError:
            return {"query_type": "simple_lookup", "requires_chart": False}

        # Extract text from response
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        try:
            return json.loads(_strip_markdown_fences(text))
        except (json.JSONDecodeError, TypeError):
            logger.warning("Classification fallback: could not parse Claude response as JSON. Raw text: %s", text)
            return {"query_type": "simple_lookup", "requires_chart": False}


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from text."""
    stripped = text.strip()
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _flatten_datasets(datasets: list) -> list[dict]:
    """Flatten list[list[dict]] into list[dict] with _dataset_index marker."""
    flat: list[dict] = []
    for idx, dataset in enumerate(datasets):
        if isinstance(dataset, list):
            for record in dataset:
                if isinstance(record, dict):
                    flat.append({**record, "_dataset_index": idx})
        elif isinstance(dataset, dict):
            flat.append({**dataset, "_dataset_index": idx})
    return flat


def _extract_all_data(tool_results: list[dict]) -> list[dict]:
    """Extract all successful tool result data entries.

    Returns a list of data dicts from tool results where ``success=True``
    and ``data`` is present.  This enables comparison queries that need
    multiple datasets (e.g. Q1 vs Q2 fetched via separate tool calls).

    ReportResponse-style dicts (with ``headers`` and ``rows`` keys) are
    automatically converted to ``list[dict]`` for uniform downstream handling.
    """
    data_list = []
    for tr in tool_results:
        result = tr.get("result", {})
        if result.get("success") is True and result.get("data") is not None:
            data = result["data"]

            # Handle ReportResponse-style dicts (headers/rows)
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                rows_as_dicts = []
                for row in data["rows"]:
                    # zip truncates to shortest; safe because headers define the schema
                    rows_as_dicts.append(dict(zip(data["headers"], row)))
                data = rows_as_dicts

            data_list.append(data)
    return data_list
