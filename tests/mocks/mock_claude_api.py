"""Mock Anthropic client for deterministic E2E testing.

Provides a drop-in replacement for ``anthropic.AsyncAnthropic`` that returns
pre-configured responses in order.  Each test pushes the expected sequence
of Claude responses and the mock pops them one by one.

Usage:
    responses = [
        make_classification_response("simple_lookup"),
        make_tool_call_response("get_trial_balance", {...}),
        make_text_response("Here is the trial balance..."),
    ]
    mock_client = MockAnthropicClient(responses)
"""

from __future__ import annotations

from collections import deque
from typing import Any

from anthropic.types import (
    ContentBlock,
    Message,
    TextBlock,
    ToolUseBlock,
    Usage,
)


# ---------------------------------------------------------------------------
# Core mock
# ---------------------------------------------------------------------------


class MockMessages:
    """Drop-in for ``anthropic.AsyncAnthropic().messages``."""

    def __init__(self, client: MockAnthropicClient) -> None:
        self.client = client

    async def create(self, **kwargs: Any) -> Message:
        self.client.call_log.append(kwargs)
        if not self.client.responses:
            raise RuntimeError(
                f"MockAnthropicClient exhausted after {len(self.client.call_log)} calls. "
                "Add more responses to the mock."
            )
        return self.client.responses.popleft()


class MockAnthropicClient:
    """Drop-in replacement for ``anthropic.AsyncAnthropic``.

    Args:
        responses: Ordered list of ``Message`` objects to return.
    """

    def __init__(self, responses: list[Message]) -> None:
        self.responses: deque[Message] = deque(responses)
        self.messages = MockMessages(self)
        self.call_log: list[dict] = []


# ---------------------------------------------------------------------------
# Response factory helpers
# ---------------------------------------------------------------------------

_USAGE = Usage(input_tokens=10, output_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0)
_COUNTER = 0


def _next_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"msg_mock_{_COUNTER:04d}"


def _tool_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"toolu_mock_{_COUNTER:04d}"


def make_text_response(text: str) -> Message:
    """A Claude response that ends the turn with a text answer."""
    return Message(
        id=_next_id(),
        type="message",
        role="assistant",
        model="claude-sonnet-4-20250514",
        content=[TextBlock(type="text", text=text)],
        stop_reason="end_turn",
        usage=_USAGE,
    )


def make_classification_response(
    query_type: str,
    requires_chart: bool = False,
    clarification_question: str | None = None,
) -> Message:
    """A Claude response containing a JSON classification."""
    import json

    payload: dict[str, Any] = {
        "query_type": query_type,
        "requires_chart": requires_chart,
    }
    if clarification_question:
        payload["clarification_question"] = clarification_question

    return make_text_response(json.dumps(payload))


def make_tool_call_response(
    tool_name: str,
    tool_input: dict[str, Any],
    extra_text: str = "",
) -> Message:
    """A Claude response requesting a tool call."""
    content: list[ContentBlock] = []
    if extra_text:
        content.append(TextBlock(type="text", text=extra_text))
    content.append(
        ToolUseBlock(
            type="tool_use",
            id=_tool_id(),
            name=tool_name,
            input=tool_input,
        )
    )
    return Message(
        id=_next_id(),
        type="message",
        role="assistant",
        model="claude-sonnet-4-20250514",
        content=content,
        stop_reason="tool_use",
        usage=_USAGE,
    )
