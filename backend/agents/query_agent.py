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
from typing import Any

import anthropic

from backend.config import settings
from backend.agents.prompts import build_query_agent_prompt
from backend.agents.tools import TALLY_TOOLS, execute_tool
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient

# Module-level client — tests patch this object.
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


class QueryAgent:
    """Fetches accounting data from TallyPrime using Claude's tool-calling loop.

    Args:
        max_tool_calls: Safety limit on the number of tool calls per execution.
    """

    def __init__(self, max_tool_calls: int = 10) -> None:
        self.max_tool_calls = max_tool_calls
        self.system_prompt = build_query_agent_prompt()

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
        # Build messages from session history + new user query
        messages = session.get_messages()
        messages.append({"role": "user", "content": user_query})

        tool_results: list[dict[str, Any]] = []
        tool_call_count = 0

        while True:
            response = await anthropic_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=self.system_prompt,
                tools=TALLY_TOOLS,
                messages=messages,
            )

            # ---- End turn: Claude produced a final text answer ----
            if response.stop_reason != "tool_use":
                final_text = _extract_text(response)
                session.add_message("user", user_query)
                session.add_message("assistant", final_text)
                return {"message": final_text, "tool_results": tool_results}

            # ---- Tool use: execute the requested tool ----
            tool_block = _find_tool_use_block(response)

            result = await execute_tool(client, tool_block.name, tool_block.input)

            tool_results.append(
                {
                    "tool_name": tool_block.name,
                    "tool_input": tool_block.input,
                    "result": result,
                }
            )

            tool_call_count += 1

            # Append the assistant's response (with tool_use block) to messages
            messages.append({"role": "assistant", "content": response.content})

            # Append the tool result as a user message
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": json.dumps(result),
                        }
                    ],
                }
            )

            # ---- Safety valve ----
            if tool_call_count >= self.max_tool_calls:
                session.add_message("user", user_query)
                msg = (
                    f"I reached the maximum number of tool calls ({self.max_tool_calls}). "
                    "Here is what I found so far based on the data retrieved."
                )
                session.add_message("assistant", msg)
                return {"message": msg, "tool_results": tool_results}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(response: Any) -> str:
    """Pull the text content from a Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _find_tool_use_block(response: Any) -> Any:
    """Find and return the first tool_use block in a Claude response."""
    for block in response.content:
        if block.type == "tool_use":
            return block
    raise ValueError("No tool_use block found in response with stop_reason='tool_use'")
