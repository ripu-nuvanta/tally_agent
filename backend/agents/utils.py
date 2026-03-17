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


# ---------------------------------------------------------------------------
# Markdown table parser for chart rendering
# ---------------------------------------------------------------------------


def _is_ordinal_header(header: str) -> bool:
    """Check if a column header suggests an ordinal/index column."""
    h = header.strip().lower().rstrip(".")
    return h in {"rank", "#", "s.no", "s no", "sr", "no", "sl", "sl no", "sl. no"}


def _is_ordinal_column(values: list, header: str) -> bool:
    """Detect ordinal columns: known headers or sequential integers."""
    if _is_ordinal_header(header):
        return True
    if len(values) < 2:
        return False
    nums = [to_numeric(v) for v in values]
    if not all(n == int(n) for n in nums if n != 0.0):
        return False
    ints = [int(n) for n in nums]
    if ints == list(range(ints[0], ints[0] + len(ints))):
        return True
    return False


def parse_markdown_table_for_chart(text: str) -> dict[str, Any] | None:
    """Parse the best markdown table from text for chart rendering.

    Finds all markdown tables, selects the one with most rows
    (tie-break: later table, then most columns), and returns
    {headers, rows} with ordinal columns stripped.

    Returns None if no suitable table found (< 2 data rows).
    """
    lines = text.split("\n")
    tables: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_block.append(stripped)
        else:
            if current_block:
                tables.append(current_block)
                current_block = []
    if current_block:
        tables.append(current_block)

    if not tables:
        return None

    parsed: list[tuple[list[str], list[list], int]] = []
    for idx, block in enumerate(tables):
        if len(block) < 3:
            continue
        header_line = block[0]
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]

        data_start = 1
        for i, line in enumerate(block[1:], 1):
            if all(cell.strip().replace("-", "").replace(":", "") == "" for cell in line.strip("|").split("|")):
                data_start = i + 1
                break

        rows = []
        for line in block[data_start:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.append(cells)

        if len(rows) >= 2:
            parsed.append((headers, rows, idx))

    if not parsed:
        return None

    best = max(parsed, key=lambda t: (len(t[1]), t[2], len(t[0])))
    headers, rows, _ = best

    skip_cols = 0
    for col_idx, header in enumerate(headers):
        col_values = [row[col_idx] for row in rows if col_idx < len(row)]
        if _is_ordinal_column(col_values, header):
            skip_cols = col_idx + 1
        else:
            break

    if skip_cols > 0:
        headers = headers[skip_cols:]
        rows = [[cell for i, cell in enumerate(row) if i >= skip_cols] for row in rows]

    converted_rows = []
    for row in rows:
        converted = []
        for i, cell in enumerate(row):
            if i == 0:
                converted.append(cell)
            else:
                num = to_numeric(cell)
                cell_stripped = cell.strip()
                if num == 0.0 and cell_stripped and cell_stripped.lower() not in _NON_NUMERIC_SENTINELS:
                    try:
                        float(cell_stripped.replace("₹", "").replace(",", "").replace("%", "").replace("*", "").strip())
                        converted.append(num)
                    except ValueError:
                        converted.append(cell_stripped)
                else:
                    converted.append(num)
        converted_rows.append(converted)

    return {"headers": headers, "rows": converted_rows}
