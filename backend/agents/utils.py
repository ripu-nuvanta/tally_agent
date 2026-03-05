"""Shared helpers for agent modules."""

from __future__ import annotations

from typing import Any


def extract_text(response: Any) -> str:
    """Pull the text content from a Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def find_tool_use_block(response: Any) -> Any | None:
    """Find and return the first tool_use block in a Claude response.

    Returns None if no tool_use block is found.
    """
    for block in response.content:
        if block.type == "tool_use":
            return block
    return None


def find_all_tool_use_blocks(response: Any) -> list[Any]:
    """Find all tool_use blocks in a Claude response."""
    return [block for block in response.content if block.type == "tool_use"]
