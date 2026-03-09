"""Query Agent — runs Claude's tool-calling loop to fetch data from TallyPrime.

The QueryAgent sends the user's question to Claude along with the available
Tally tools.  Claude may request one or more tool calls (e.g. get_trial_balance,
search_ledger) which the agent executes via the Tally Bridge, feeding results
back until Claude produces a final text answer.

Exports:
    QueryAgent  — The main agent class.
    anthropic_client — Module-level AsyncAnthropic instance (patched in tests).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.agents.prompts import build_query_agent_prompt
from backend.agents.tools import TALLY_TOOLS, execute_tool, DATE_TOOLS, execute_date_tool
from backend.agents.analysis_agent import ANALYSIS_TOOLS, execute_analysis_tool
from backend.agents.utils import extract_text, find_all_tool_use_blocks
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient

# Names of analysis tools so we can dispatch sync vs async
_ANALYSIS_TOOL_NAMES = {t["name"] for t in ANALYSIS_TOOLS}

# Names of date tools (also sync)
_DATE_TOOL_NAMES = {t["name"] for t in DATE_TOOLS}

# Combined tool list: Tally (data fetching) + Analysis (computation) + Date (resolution)
_ALL_QUERY_TOOLS = TALLY_TOOLS + ANALYSIS_TOOLS + DATE_TOOLS

# Module-level client — tests patch this object.
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


class QueryAgent:
    """Fetches accounting data from TallyPrime using Claude's tool-calling loop.

    Args:
        max_tool_calls: Safety limit on the number of tool calls per execution.
    """

    def __init__(self, max_tool_calls: int = 25) -> None:
        self.max_tool_calls = max_tool_calls

    async def execute(
        self,
        user_query: str,
        client: TallyClient,
        session: SessionContext,
    ) -> dict[str, Any]:
        """Run the query agent loop.

        Returns:
            {
                "message": str,          # Claude's final text answer
                "tool_results": [        # Each tool call made during the loop
                    {
                        "tool_name": str,
                        "tool_input": dict,
                        "result": dict,
                    },
                    ...
                ],
            }
        """
        # Build system prompt with current date
        from datetime import date as date_cls
        from backend.utils.date_utils import format_for_tally
        current_date = format_for_tally(date_cls.today())
        system_prompt = build_query_agent_prompt(current_date)

        # Build messages from session history + new user query
        messages = session.get_messages()
        messages.append({"role": "user", "content": user_query})

        tool_results: list[dict[str, Any]] = []
        tool_call_count = 0
        turn = 0

        logger.info("QueryAgent start — query=%r", user_query)

        while True:
            turn += 1
            logger.info("QueryAgent turn %d — sending %d messages to Claude", turn, len(messages))

            try:
                response = await anthropic_client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=_ALL_QUERY_TOOLS,
                    messages=messages,
                )
            except anthropic.APIError as exc:
                error_msg = f"Claude API error: {exc}"
                logger.error("QueryAgent turn %d — API error: %s", turn, exc)
                session.add_message("user", user_query)
                session.add_message("assistant", error_msg)
                return {"message": error_msg, "tool_results": tool_results}

            logger.info(
                "QueryAgent turn %d — stop_reason=%s, content_blocks=%d",
                turn, response.stop_reason, len(response.content),
            )

            # Log Claude's text content for this turn (thinking / reasoning before tool calls)
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    logger.debug("QueryAgent turn %d — Claude text:\n%s", turn, block.text)

            # ---- End turn: Claude produced a final text answer ----
            if response.stop_reason != "tool_use":
                final_text = extract_text(response)
                logger.info("QueryAgent turn %d — final answer (%d chars)", turn, len(final_text))
                logger.debug("QueryAgent turn %d — FINAL ANSWER:\n%s", turn, final_text)
                session.add_message("user", user_query)
                session.add_message("assistant", final_text)
                return {"message": final_text, "tool_results": tool_results}

            # ---- Tool use: execute all requested tools ----
            tool_blocks = find_all_tool_use_blocks(response)
            logger.info("QueryAgent turn %d — %d tool call(s) requested", turn, len(tool_blocks))

            tool_result_entries = []
            for tool_block in tool_blocks:
                logger.info(
                    "QueryAgent turn %d — calling tool %r with input:\n%s",
                    turn, tool_block.name, json.dumps(tool_block.input, default=str, indent=2),
                )

                if tool_block.name in _ANALYSIS_TOOL_NAMES:
                    result = execute_analysis_tool(tool_block.name, tool_block.input)
                elif tool_block.name in _DATE_TOOL_NAMES:
                    result = execute_date_tool(tool_block.name, tool_block.input)
                else:
                    result = await execute_tool(client, tool_block.name, tool_block.input)

                # Log the full tool result
                logger.debug(
                    "QueryAgent turn %d — tool %r full result:\n%s",
                    turn, tool_block.name, json.dumps(result, default=str, indent=2),
                )

                tool_results.append(
                    {
                        "tool_name": tool_block.name,
                        "tool_input": tool_block.input,
                        "result": result,
                    }
                )

                tool_result_entries.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result),
                    }
                )

            tool_call_count += len(tool_blocks)

            # Append the assistant's response (with all tool_use blocks) to messages
            messages.append({"role": "assistant", "content": response.content})

            # Append all tool results in a single user message
            messages.append(
                {
                    "role": "user",
                    "content": tool_result_entries,
                }
            )

            # ---- Safety valve ----
            if tool_call_count >= self.max_tool_calls:
                logger.warning(
                    "QueryAgent — hit max tool calls (%d), stopping", self.max_tool_calls,
                )
                session.add_message("user", user_query)
                msg = (
                    f"I reached the maximum number of tool calls ({self.max_tool_calls}). "
                    "Here is what I found so far based on the data retrieved."
                )
                session.add_message("assistant", msg)
                return {"message": msg, "tool_results": tool_results}


