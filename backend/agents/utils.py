"""Shared helpers for agent modules."""

from __future__ import annotations

import json
from typing import Any

STRUCTURED_RESULT_PREFIX = "STRUCTURED_RESULT:"


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


def find_custom_tool_use_blocks(response: Any) -> list[Any]:
    """Find only user-defined tool_use blocks (not server_tool_use)."""
    return [block for block in response.content if block.type == "tool_use"]


def extract_code_execution_results(response: Any) -> list[dict[str, Any]]:
    """Extract code execution results from response for logging."""
    results: list[dict[str, Any]] = []
    for block in response.content:
        if block.type == "server_tool_use":
            inp = block.input
            code = inp.get("code", "") if isinstance(inp, dict) else getattr(inp, "code", "")
            results.append({"type": "code_written", "code": code})
        elif block.type == "code_execution_tool_result":
            results.append({
                "type": "code_result",
                "stdout": getattr(block, "stdout", ""),
                "stderr": getattr(block, "stderr", ""),
                "return_code": getattr(block, "return_code", None),
            })
    return results


def extract_structured_from_code_execution(response: Any) -> dict[str, Any] | None:
    """Extract {headers, rows} from code_execution stdout if present."""
    for block in response.content:
        if block.type == "code_execution_tool_result":
            stdout = getattr(block, "stdout", "")
            for line in reversed(stdout.strip().splitlines()):
                if line.startswith(STRUCTURED_RESULT_PREFIX):
                    try:
                        data = json.loads(line[len(STRUCTURED_RESULT_PREFIX):])
                        if isinstance(data, dict) and "headers" in data and "rows" in data:
                            return data
                    except json.JSONDecodeError:
                        pass
    return None
