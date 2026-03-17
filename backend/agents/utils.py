"""Shared helpers for agent modules."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

STRUCTURED_RESULT_PREFIX = "STRUCTURED_RESULT:"


def extract_text(response: Any) -> str:
    """Pull the final text content from a Claude response.

    Returns the *last* text block, not the first.  With code_execution
    responses the first text block is often a preamble ("Let me compute…")
    while the actual answer appears after the code_execution_tool_result.
    """
    last_text = ""
    for block in response.content:
        if block.type == "text":
            last_text = block.text
    return last_text


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
    """Extract {headers, rows} from code_execution stdout if present.

    Searches ALL lines in stdout (not just the last) to handle cases
    where Claude prints debug output after the STRUCTURED_RESULT line.
    """
    found_code_exec = False
    for block in response.content:
        if block.type == "code_execution_tool_result":
            found_code_exec = True
            stdout = getattr(block, "stdout", "")
            for line in stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith(STRUCTURED_RESULT_PREFIX):
                    try:
                        data = json.loads(stripped[len(STRUCTURED_RESULT_PREFIX):])
                        if isinstance(data, dict) and "headers" in data and "rows" in data:
                            return data
                        logger.warning("STRUCTURED_RESULT parsed but missing headers/rows: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)
                    except json.JSONDecodeError as exc:
                        logger.warning("STRUCTURED_RESULT JSON parse error: %s — line: %s", exc, stripped[:200])
    if found_code_exec:
        logger.warning("code_execution ran but no valid STRUCTURED_RESULT found in stdout")
    return None


# ---------------------------------------------------------------------------
# Shared numeric coercion (used by ChartAgent and markdown table parser)
# ---------------------------------------------------------------------------

# Regex to strip emoji codepoints
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0000200D"
    "\U000025B2-\U000025BD"
    "\U00002B06-\U00002B07"
    "\U000027A1"
    "]+",
    flags=re.UNICODE,
)

_NON_NUMERIC_SENTINELS = {"—", "–", "-", "n/a", "nil", "none", ""}


def to_numeric(val: Any) -> float:
    """Coerce a value to float, stripping currency, emoji, arrows, and symbols.

    Shared converter used by both the markdown table parser and ChartAgent.
    Returns 0.0 for non-numeric text.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return 0.0

    cleaned = _EMOJI_RE.sub("", val)
    cleaned = cleaned.replace("\u2212", "-")
    cleaned = cleaned.replace("₹", "").replace(",", "").replace("*", "").replace("%", "")
    cleaned = cleaned.replace(" pp", "")
    cleaned = cleaned.strip()

    if cleaned.lower() in _NON_NUMERIC_SENTINELS:
        return 0.0

    if cleaned.startswith("(") and cleaned.endswith(")"):
        return 0.0

    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    try:
        return float(cleaned)
    except ValueError:
        return 0.0
